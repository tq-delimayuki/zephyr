#!/usr/bin/env python3
#
# Copyright (c) 2018 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

"""
Script to generate a linker script organizing application memory partitions

Applications may declare build-time memory domain partitions with
K_APPMEM_PARTITION_DEFINE, and assign globals to them using K_APP_DMEM
or K_APP_BMEM macros. For each of these partitions, we need to
route all their data into appropriately-sized memory areas which meet the
size/alignment constraints of the memory protection hardware.

This linker script is created very early in the build process, before
the build attempts to link the kernel binary, as the linker script this
tool generates is a necessary pre-condition for kernel linking. We extract
the set of memory partitions to generate by looking for variables which
have been assigned to input sections that follow a defined naming convention.
We also allow entire libraries to be pulled in to assign their globals
to a particular memory partition via command line directives.

This script takes as inputs:

- The base directory to look for compiled objects
- key/value pairs mapping static library files to what partitions their globals
  should end up in.

The output is either a linker script fragment or linker-script generator
fragments containing the definition of the app shared memory section, which
is further divided, for each partition found, into data and BSS for each
partition.
"""

#The linker script fragments looks something like this:
# SECTION_PROLOGUE(_APP_SMEM_SECTION_NAME,,)
# 	{
# 		APP_SHARED_ALIGN;
# 		_app_smem_start = .;

# 		/* Auto generated code do not modify */
# 		SMEM_PARTITION_ALIGN(z_data_smem_ztest_mem_partition_bss_end - z_data_smem_ztest_mem_partition_part_start);
# 		z_data_smem_ztest_mem_partition_part_start = .;
# 		KEEP(*(data_smem_ztest_mem_partition_data*))

# 		z_data_smem_ztest_mem_partition_bss_start = .;
# 		KEEP(*(data_smem_ztest_mem_partition_bss*))

# 		z_data_smem_ztest_mem_partition_bss_end = .;
# 		SMEM_PARTITION_ALIGN(z_data_smem_ztest_mem_partition_bss_end - z_data_smem_ztest_mem_partition_part_start);
# 		z_data_smem_ztest_mem_partition_part_end = .;

# 		/* Auto generated code do not modify */
# 		SMEM_PARTITION_ALIGN(z_data_smem_z_libc_partition_bss_end - z_data_smem_z_libc_partition_part_start);
# 		z_data_smem_z_libc_partition_part_start = .;
# 		KEEP(*(data_smem_z_libc_partition_data*))

# 		z_data_smem_z_libc_partition_bss_start = .;
# 		KEEP(*(data_smem_z_libc_partition_bss*))

# 		z_data_smem_z_libc_partition_bss_end = .;
# 		SMEM_PARTITION_ALIGN(z_data_smem_z_libc_partition_bss_end - z_data_smem_z_libc_partition_part_start);
# 		z_data_smem_z_libc_partition_part_end = .;

# 		APP_SHARED_ALIGN;
# 		_app_smem_end = .;
# 	} GROUP_DATA_LINK_IN(RAMABLE_REGION, ROMABLE_REGION)

# 	z_data_smem_ztest_mem_partition_part_size = z_data_smem_ztest_mem_partition_part_end - z_data_smem_ztest_mem_partition_part_start;
# 	z_data_smem_ztest_mem_partition_bss_size = z_data_smem_ztest_mem_partition_bss_end - z_data_smem_ztest_mem_partition_bss_start;

# 	z_data_smem_z_libc_partition_part_size = z_data_smem_z_libc_partition_part_end - z_data_smem_z_libc_partition_part_start;
# 	z_data_smem_z_libc_partition_bss_size = z_data_smem_z_libc_partition_bss_end - z_data_smem_z_libc_partition_bss_start;

# the linker script generator fragments looks something like this:
# There is a zephyr_linker_group() called APP_SMEM_GROUP for these sections
# defined in linker.cmake
# _APP_SMEM_SECTION_NAME is #defined in sections.h to "app_smem". Ideally we should have that here too.
#
# zephyr_linker_section(NAME _APP_SMEM_SECTION_NAME GROUP APP_SMEM_GROUP NOINPUT ALIGN_WITH_INPUT)
#   zephyr_linker_section_configure(
#     SECTION
#     _APP_SMEM_SECTION_NAME
#     SYMBOLS
#     _app_smem_start
#     )
#   zephyr_linker_section_configure(
#     SECTION
#     _APP_SMEM_SECTION_NAME
#     INPUT
#     "data_smem_ztest_mem_partition_data*"
#     KEEP
#     SYMBOLS
#     z_data_smem_ztest_mem_partition_part_start
#     )
#   zephyr_linker_section_configure(
#     SECTION
#     _APP_SMEM_SECTION_NAME
#     INPUT
#     "data_smem_ztest_mem_partition_bss*"
#     KEEP
#     SYMBOLS
#     z_data_smem_ztest_mem_partition_bss_start
#     z_data_smem_ztest_mem_partition_bss_end
#     )
#   zephyr_linker_section_configure(
#     SECTION
#     _APP_SMEM_SECTION_NAME
#     SYMBOLS
#     z_data_smem_ztest_mem_partition_part_end
#     )

#   zephyr_linker_section_configure(
#     SECTION
#     _APP_SMEM_SECTION_NAME
#     INPUT
#     "data_smem_z_libc_partition_data*"
#     KEEP
#     SYMBOLS
#     z_data_smem_z_libc_partition_part_start
#     )
#   zephyr_linker_section_configure(
#     SECTION
#     _APP_SMEM_SECTION_NAME
#     INPUT
#     "data_smem_z_libc_partition_bss*"
#     KEEP
#     SYMBOLS
#     z_data_smem_z_libc_partition_bss_start
#     z_data_smem_z_libc_partition_bss_end
#     )
#   zephyr_linker_section_configure(
#     SECTION
#     _APP_SMEM_SECTION_NAME
#     SYMBOLS
#     z_data_smem_z_libc_partition_part_end
#     )
#   zephyr_linker_section_configure(
#     SECTION
#     _APP_SMEM_SECTION_NAME
#     SYMBOLS
#     _app_smem_end
#     )
#   zephyr_linker_symbol(
#     SYMBOL
#     z_data_smem_ztest_mem_partition_part_size
#     EXPR
#     "(@z_data_smem_ztest_mem_partition_part_end@ - @z_data_smem_ztest_mem_partition_part_start@)"
#     )
#   zephyr_linker_symbol(
#     SYMBOL
#     z_data_smem_ztest_mem_partition_bss_size
#     EXPR
#     "(@z_data_smem_ztest_mem_partition_bss_end@ - @z_data_smem_ztest_mem_partition_bss_start@)"
#     )

#   zephyr_linker_symbol(
#     SYMBOL
#     z_data_smem_z_libc_partition_part_size
#     EXPR
#     "(@z_data_smem_z_libc_partition_part_end@ - @z_data_smem_z_libc_partition_part_start@)"
#     )
#   zephyr_linker_symbol(
#     SYMBOL
#     z_data_smem_z_libc_partition_bss_size
#     EXPR
#     "(@z_data_smem_z_libc_partition_bss_end@ - @z_data_smem_z_libc_partition_bss_start@)"
#     )


import sys
import argparse
import json
import os
import re
from collections import OrderedDict
from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection
import elftools.common.exceptions

SZ = 'size'
SRC = 'sources'
LIB = 'libraries'

# This script will create sections and linker variables to place the
# application shared memory partitions.
# these are later read by the macros defined in app_memdomain.h for
# initialization purpose when USERSPACE is enabled.

class LDScriptTemlate:
    data_template = """
            /* Auto generated code do not modify */
            SMEM_PARTITION_ALIGN(z_data_smem_{partition}_bss_end - z_data_smem_{partition}_part_start);
            z_data_smem_{partition}_part_start = .;
            KEEP(*(data_smem_{partition}_data*))
    """

    library_data_template = """
            \"*{lib}:*\"(.data .data.* .sdata .sdata.*)
    """

    bss_template = """
            z_data_smem_{partition}_bss_start = .;
            KEEP(*(data_smem_{partition}_bss*))
    """

    library_bss_template = """
            \"*{lib}:*\"(.bss .bss.* .sbss .sbss.* COMMON COMMON.*)
    """

    footer_template = """
            z_data_smem_{partition}_bss_end = .;
            SMEM_PARTITION_ALIGN(z_data_smem_{partition}_bss_end - z_data_smem_{partition}_part_start);
            z_data_smem_{partition}_part_end = .;
    """

    linker_start_seq = """
        SECTION_PROLOGUE(_APP_SMEM{SECTION}_SECTION_NAME,,)
        {{
            APP_SHARED_ALIGN;
            _app_smem{section}_start = .;
    """

    linker_end_seq = """
            APP_SHARED_ALIGN;
            _app_smem{section}_end = .;
        }} GROUP_DATA_LINK_IN(RAMABLE_REGION, ROMABLE_REGION)
    """

    empty_app_smem = """
        SECTION_PROLOGUE(_APP_SMEM{SECTION}_SECTION_NAME,,)
        {{
    #ifdef EMPTY_APP_SHARED_ALIGN
            EMPTY_APP_SHARED_ALIGN;
    #endif
            _app_smem{section}_start = .;
            _app_smem{section}_end = .;
        }} GROUP_DATA_LINK_IN(RAMABLE_REGION, ROMABLE_REGION)
    """

    size_cal_string = """
        z_data_smem_{partition}_part_size = z_data_smem_{partition}_part_end - z_data_smem_{partition}_part_start;
        z_data_smem_{partition}_bss_size = z_data_smem_{partition}_bss_end - z_data_smem_{partition}_bss_start;
    """

def cmake_list_append(list, props):
    tokens = [fr"{key}\;{value}" for key, value in props.items()]
    stuff = r"\;".join(tokens)
    return """list(APPEND """+ list + """ \"{{""" + stuff + """}}\")\n"""

def zephyr_linker_section(name, group, align = None, noinput = True, align_with_input = True, hidden = False, noinit = False):
    props = {"""NAME""": name, """GROUP""": group}
    if align :
        props['ALIGN'] = align
    #The bool flags are always there:
    props['NOIPUT'] = noinput
    props['ALIGN_WITH_INPUT'] = align_with_input
    props['HIDDEN'] = hidden
    props['NOINIT'] = noinit
    return cmake_list_append("SECTIONS", props)

def zephyr_linker_section_configure(section, input = None, symbols = None, align = None, any = False, first = False, keep = False):
    props = {"SECTION": section}
    if input:
        props["INPUT"] = input
    #ANY\;FALSE\;FIRST\;FALSE\;KEEP\;FALSE\
    props['ANY'] = any
    props['FIRST'] = first
    props['KEEP'] = keep
    if symbols:
        props["SYMBOLS"] = symbols
    if align:
        props["ALIGN"] = align
    return cmake_list_append("SECTION_SETTINGS", props)

def zephyr_linker_symbol(symbol, expr) :
    return cmake_list_append("SYMBOLS", {'SYMBOL': symbol, 'EXPR':expr})

class CmakeTemplate:
    section_name = "@_APP_SMEM{SECTION}_SECTION_NAME@"
    data_template = (
        zephyr_linker_section_configure(section=section_name, align="@SMEM_PARTITION_ALIGN_BYTES@")+
        zephyr_linker_section_configure(section=section_name, input="data_smem_{partition}_data*", symbols="z_data_smem_{partition}_part_start", keep=True)
    )

    library_data_template = zephyr_linker_section_configure(section=section_name, input="*{lib}:*(.data .data.* .sdata .sdata.*)")

    bss_template = (
        zephyr_linker_section_configure(section=section_name, input="data_smem_{partition}_bss*", symbols="z_data_smem_{partition}_bss_start", keep=True)
    )

    library_bss_template = zephyr_linker_section_configure(section=section_name, input="*{lib}:*(.bss .bss.* .sbss .sbss.* COMMON COMMON.*)")

    footer_template = (
        zephyr_linker_section_configure(section=section_name, symbols="z_data_smem_{partition}_bss_end", keep=True) +
        zephyr_linker_section_configure(section=section_name, align="@SMEM_PARTITION_ALIGN_BYTES@") +
        zephyr_linker_section_configure(section=section_name, symbols="z_data_smem_{partition}_part_end", keep=True)
    )

    linker_start_seq = (
        zephyr_linker_section(name=section_name, group="APP_SMEM_GROUP", noinput=True, align_with_input=True) +
        zephyr_linker_section_configure(section=section_name, align="@APP_SHARED_ALIGN_BYTES@", symbols="_app_smem{section}_start"))

    linker_end_seq = (
        zephyr_linker_section_configure(section=section_name, align="@APP_SHARED_ALIGN_BYTES@") +
        zephyr_linker_section_configure(section=section_name, symbols="_app_smem{section}_end") )

    empty_app_smem = (
        zephyr_linker_section(name=section_name, group="APP_SMEM_GROUP", align="@APP_SHARED_ALIGN_BYTES@", noinput=True, align_with_input=True) +
        zephyr_linker_section_configure(section = section_name, symbols="_app_smem{section}_start") +
        zephyr_linker_section_configure(section = section_name, symbols="_app_smem{section}_end") )

    size_cal_string = (
        zephyr_linker_symbol(symbol='z_data_smem_{partition}_part_size', expr='@z_data_smem_{partition}_part_end@ - @z_data_smem_{partition}_part_start@') +
        zephyr_linker_symbol(symbol='z_data_smem_{partition}_bss_size', expr='@z_data_smem_{partition}_bss_end@ - @z_data_smem_{partition}_bss_start@'))

section_regex = re.compile(r'data_smem_([A-Za-z0-9_]*)_(data|bss)*')

elf_part_size_regex = re.compile(r'z_data_smem_(.*)_part_size')

def find_obj_file_partitions(filename, partitions):
    with open(filename, 'rb') as f:
        try:
            full_lib = ELFFile(f)
        except elftools.common.exceptions.ELFError as e:
            exit(f"Error: {filename}: {e}")

        if not full_lib:
            sys.exit("Error parsing file: " + filename)

        sections = [x for x in full_lib.iter_sections()]
        for section in sections:
            m = section_regex.match(section.name)
            if not m:
                continue

            partition_name = m.groups()[0]
            if partition_name not in partitions:
                partitions[partition_name] = {SZ: section.header.sh_size}

                if args.verbose:
                    partitions[partition_name][SRC] = filename

            else:
                partitions[partition_name][SZ] += section.header.sh_size


    return partitions


def parse_obj_files(partitions):
    # Iterate over all object files to find partitions
    for dirpath, _, files in os.walk(args.directory):
        for filename in files:
            if re.match(r".*\.obj$", filename):
                fullname = os.path.join(dirpath, filename)
                fsize = os.path.getsize(fullname)
                if fsize != 0:
                    find_obj_file_partitions(fullname, partitions)


def parse_compile_command_file(partitions):
    # Iterate over all entries to find object files.
    # Thereafter process each object file to find partitions
    object_pattern = re.compile(r'-o\s+(\S*)')
    with open(args.compile_commands_file, 'rb') as f:
        commands = json.load(f)
        for command in commands:
            build_dir = command.get('directory')
            compile_command = command.get('command')
            compile_arg = object_pattern.search(compile_command)
            obj_file = None if compile_arg is None else compile_arg.group(1)
            if obj_file:
                fullname = os.path.join(build_dir, obj_file)
                # Because of issue #40635, then not all objects referenced by
                # the compile_commands.json file may be available, therefore
                # only include existing files.
                if os.path.exists(fullname):
                    find_obj_file_partitions(fullname, partitions)


def parse_elf_file(partitions):
    with open(args.elf, 'rb') as f:
        try:
            elffile = ELFFile(f)
        except elftools.common.exceptions.ELFError as e:
            exit(f"Error: {args.elf}: {e}")

        symbol_tbls = [s for s in elffile.iter_sections()
                       if isinstance(s, SymbolTableSection)]

        for section in symbol_tbls:
            for symbol in section.iter_symbols():
                if symbol['st_shndx'] != "SHN_ABS":
                    continue

                x = elf_part_size_regex.match(symbol.name)
                if not x:
                    continue

                partition_name = x.groups()[0]
                size = symbol['st_value']
                if partition_name not in partitions:
                    partitions[partition_name] = {SZ: size}

                    if args.verbose:
                        partitions[partition_name][SRC] = args.elf

                else:
                    partitions[partition_name][SZ] += size

def generate_final(linker_file, partitions, lnkr_sect=""):
    if linker_file.endswith(".ld"):
        template = LDScriptTemlate
    else:
        template = CmakeTemplate
    generate_final_linker(template, linker_file, partitions, lnkr_sect)

def generate_final_linker(template, linker_file, partitions, lnkr_sect):
    string = ""
    props = { 'section' : lnkr_sect, 'SECTION' : lnkr_sect.upper() }
    if len(partitions) > 0:
        string = template.linker_start_seq.format(**props)
        size_string = ''
        for partition, item in partitions.items():
            part_props = props
            part_props["partition"] = partition
            string += template.data_template.format(**part_props)
            if LIB in item:
                for lib in item[LIB]:
                    lib_props = part_props
                    lib_props["lib"] = lib
                    string += template.library_data_template.format(**lib_props)
            string += template.bss_template.format(**part_props)
            if LIB in item:
                for lib in item[LIB]:
                    lib_props = part_props
                    lib_props["lib"] = lib
                    string += template.library_bss_template.format(**lib_props)
            string += template.footer_template.format(**part_props)
            size_string += template.size_cal_string.format(**part_props)

        string += template.linker_end_seq.format(**props)
        string += size_string
    else:
        string = template.empty_app_smem.format(**props) #lnkr_sect, lnkr_sect.upper())

    with open(linker_file, "w") as fw:
        fw.write(string)

def parse_args():
    global args
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    parser.add_argument("-d", "--directory", required=False, default=None,
                        help="Root build directory")
    parser.add_argument("-e", "--elf", required=False, default=None,
                        help="ELF file")
    parser.add_argument("-f", "--compile-commands-file", required=False,
                        default=None, help="CMake compile commands file")
    parser.add_argument("-o", "--output", required=False,
                        help="Output ld file")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="Verbose Output")
    parser.add_argument("-l", "--library", nargs=2, action="append", default=[],
                        metavar=("LIBRARY", "PARTITION"),
                        help="Include globals for a particular library or object filename into a designated partition")
    parser.add_argument("--pinoutput", required=False,
                        help="Output ld file for pinned sections")
    parser.add_argument("--pinpartitions", action="store", required=False, default="",
                        help="Comma separated names of partitions to be pinned in physical memory")

    args, _ = parser.parse_known_args()


def main():
    parse_args()
    partitions = {}

    if args.directory is not None:
        parse_obj_files(partitions)
    if args.compile_commands_file is not None:
        parse_compile_command_file(partitions)
    elif args.elf is not None:
        parse_elf_file(partitions)
    else:
        return

    for lib, ptn in args.library:
        if ptn not in partitions:
            partitions[ptn] = {}

        if LIB not in partitions[ptn]:
            partitions[ptn][LIB] = [lib]
        else:
            partitions[ptn][LIB].append(lib)

    if args.pinoutput:
        pin_part_names = args.pinpartitions.split(',')

        generic_partitions = {key: value for key, value in partitions.items()
                              if key not in pin_part_names}
        pinned_partitions = {key: value for key, value in partitions.items()
                             if key in pin_part_names}
    else:
        generic_partitions = partitions

    # Sample partitions.items() list before sorting:
    #   [ ('part1', {'size': 64}), ('part3', {'size': 64}, ...
    #     ('part0', {'size': 334}) ]
    decreasing_tuples = sorted(generic_partitions.items(),
                           key=lambda x: (x[1][SZ], x[0]), reverse=True)

    partsorted = OrderedDict(decreasing_tuples)

    generate_final(args.output, partsorted)

    if args.verbose:
        print("Partitions retrieved:")
        for key in partsorted:
            print("    {0}: size {1}: {2}".format(key,
                                                  partsorted[key][SZ],
                                                  partsorted[key][SRC]))

    if args.pinoutput:
        decreasing_tuples = sorted(pinned_partitions.items(),
                                   key=lambda x: (x[1][SZ], x[0]), reverse=True)

        partsorted = OrderedDict(decreasing_tuples)

        generate_final(args.pinoutput, partsorted, lnkr_sect="_pinned")
        if args.verbose:
            print("Pinned partitions retrieved:")
            for key in partsorted:
                print("    {0}: size {1}: {2}".format(key,
                                                    partsorted[key][SZ],
                                                    partsorted[key][SRC]))


if __name__ == '__main__':
    main()
