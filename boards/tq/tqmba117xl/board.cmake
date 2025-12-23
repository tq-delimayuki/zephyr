# Copyright (c) 2025 TQ-Systems GmbH <license@tq-group.com>, D-82229 Seefeld, Germany.
# Author: Isaac L. L. Yuki
#
# SPDX-License-Identifier: Apache-2.0
#

if(CONFIG_SOC_MIMXRT1176_CM7)
 board_runner_args(jlink "--reset-after-load")

include(${ZEPHYR_BASE}/boards/common/jlink.board.cmake)
endif()
