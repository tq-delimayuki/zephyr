/*
 * Copyright (c) 2025 TQ-Systems GmbH <license@tq-group.com>, D-82229 Seefeld, Germany.
 * Author: Isaac L. L. Yuki
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*******************************************************************************
 * Includes
 ******************************************************************************/

#include "PF5020.h"
#include <zephyr/device.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/kernel.h>
#include <zephyr/platform/hooks.h>
#include <zephyr/drivers/gpio.h>
#include "fsl_clock.h"

#if (defined(DISPLAY_TM070) && (DISPLAY_TM070 == 1))
#include "tqmba117xl_tm070_support.h"
#endif

/*******************************************************************************
 * Definitions
 ******************************************************************************/

#define LCD_CTR_NODE DT_ALIAS(lcd_control)
#if !DT_NODE_HAS_STATUS_OKAY(LCD_CTR_NODE)
#error "lcd-control devicetree alias is not defined"
#endif

/*
 * Check if devicetree node identifier is defined
 */
#if DT_NODE_HAS_STATUS(DT_ALIAS(i2c_peripheral_6), okay)
#define I2C_NODE DT_ALIAS(i2c_peripheral_6)
#else
#error "I2C6 Peripheral isn't set."
#endif

#define PF5020_ADDRESS 0x08

/*******************************************************************************
 * Variables
 ******************************************************************************/

static const struct device *i2c_dev;
static const struct gpio_dt_spec mipi_select = GPIO_DT_SPEC_GET_BY_IDX(LCD_CTR_NODE, gpios, 0);

/*******************************************************************************
 * Prototypes
 ******************************************************************************/

static uint32_t PF5020_transfer(const void *peripheral, uint8_t regAddress, size_t regAddressSize,
				uint8_t *buffer, uint8_t dataSize,
				PF5020_TransferDirection_t transferDirection);

/*******************************************************************************
 * Code
 ******************************************************************************/

/*
 * \brief  This is the main application entry point where system is
 * initialized and all system components are started.
 * Look inside the Zephyr documentation for more information about this hook.
 */
void soc_late_init_hook(void)
{
	float voltage;
	uint32_t sysClock = CLOCK_GetRootClockFreq(kCLOCK_Root_M7);

	printk("\r\nCore Clock Frequency: %u Hz\r\n", sysClock);
	sysClock = CLOCK_GetRootClockFreq(kCLOCK_Root_Semc);
	printk("SEMC Clock Frequency: %u Hz\r\n", sysClock);

	i2c_dev = DEVICE_DT_GET(I2C_NODE);

	PF5020_Handle_t PMIC = {.transfer = PF5020_transfer, .peripheral = i2c_dev};

	PF5020_setCoreVoltage(PMIC_VDD_SOC_1V100, &PMIC);
	PF5020_readCoreVoltage(&voltage, &PMIC);
	printk("PMIC set to: %fV\r\n", (double)voltage);
}

/*
 * \brief This function is called after the board initialization is complete.
 * Look inside the Zephyr documentation for more information about this hook.
 */
void board_late_init_hook(void)
{
	/* Set MIPI_DSI as the default display interface */
	uint8_t status = gpio_pin_configure_dt(&mipi_select, GPIO_OUTPUT_INACTIVE);

#if (defined(DISPLAY_TM070) && (DISPLAY_TM070 == 1))
	/*select LVDS if selected by shield */
	status = gpio_pin_configure_dt(&mipi_select, GPIO_OUTPUT_ACTIVE);
	BOARD_PrepareDisplayController();
	printk("Initialized LVDS bridge\r\n");
#endif
	if (status < 0) {
		printk("Failed to configure the 'MIPI_SELECT' pin.\n");
	}
}

/*
 * \brief This is the transfer function that is used by the driver.
 * \note Parameters are described in the drivers function.
 */
static uint32_t PF5020_transfer(const void *peripheral, uint8_t regAddress, size_t regAddressSize,
				uint8_t *buffer, uint8_t dataSize,
				PF5020_TransferDirection_t transferDirection)
{
	status_t status = kStatus_NoTransferInProgress;

	struct i2c_msg msg;

	switch (transferDirection) {
	case PF5020_READ:
		msg.flags = I2C_MSG_WRITE;
		msg.buf = &regAddress;
		msg.len = regAddressSize;
		status = i2c_transfer(peripheral, &msg, 1, PF5020_ADDRESS);
		msg.buf = buffer;
		msg.len = dataSize;
		msg.flags = I2C_MSG_READ | I2C_MSG_STOP;
		status = i2c_transfer(peripheral, &msg, 1, PF5020_ADDRESS);
		break;

	case PF5020_WRITE:
		status = i2c_burst_write(peripheral, PF5020_ADDRESS, regAddress, buffer, dataSize);
		break;

	default:
		status = 1;
	}
	return (uint32_t)status;
}
