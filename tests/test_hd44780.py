#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2020 Richard Hull and contributors
# See LICENSE.rst for details.

"""
Tests for the :py:class:`luma.lcd.device.hd44780` device.
"""

from luma.lcd.device import hd44780
from luma.core.render import canvas
from luma.core.util import bytes_to_nibbles
from luma.lcd.const import hd44780 as CONST

from PIL import Image, ImageDraw
from unittest.mock import Mock, call

serial = Mock(unsafe=True, _bitmode=4)
gpio = Mock()


def test_init_4bitmode():
    """
    Test initialization of display using 4 bit mode
    """
    hd44780(serial, gpio=gpio)

    to_8 = \
        [call(0x3), call(0x3), call(0x3, 0x3)] * 3
    to_4 = \
        [call(0x3), call(0x3), call(0x3, 0x02)]

    fs = [CONST.FUNCTIONSET | CONST.DL4 | CONST.LINES2]

    calls = \
        to_8 + \
        to_4 + \
        [call(*bytes_to_nibbles(fs))] + \
        [call(*bytes_to_nibbles([CONST.DISPLAYOFF]))] + \
        [call(*bytes_to_nibbles([CONST.ENTRY]))] + \
        [call(*bytes_to_nibbles([CONST.DISPLAYON]))] + \
        [call(*bytes_to_nibbles([CONST.DDRAMADDR]))] + \
        [call(*bytes_to_nibbles([CONST.DDRAMADDR | CONST.LINES[1]]))] + \
        [call(*bytes_to_nibbles([CONST.CLEAR]))]

    serial.command.assert_has_calls(calls)

    # Data to clear the screen
    calls = \
        [call(bytes_to_nibbles([0x20] * 16))] + \
        [call(bytes_to_nibbles([0x20] * 16))]

    serial.data.assert_has_calls(calls)


def test_init_8bitmode():
    """
    Test initialization of display using 4 bit mode
    """
    serial._bitmode = 8
    hd44780(serial, gpio=gpio)

    to_8 = \
        [call(0x30)] * 3

    fs = [CONST.FUNCTIONSET | CONST.DL8 | CONST.LINES2]

    calls = \
        to_8 + \
        [call(*fs)] + \
        [call(*[CONST.DISPLAYOFF])] + \
        [call(*[CONST.ENTRY])] + \
        [call(*[CONST.DISPLAYON])] + \
        [call(*[CONST.DDRAMADDR])] + \
        [call(*[CONST.DDRAMADDR | CONST.LINES[1]])] + \
        [call(*[CONST.CLEAR])]

    serial.command.assert_has_calls(calls)

    # Data to clear the screen
    calls = \
        [call([0x20] * 16)] + \
        [call([0x20] * 16)]

    serial.data.assert_has_calls(calls)


def test_display():
    """
    Test the display with a line of text and a rectangle to demonstrate correct
    functioning of the auto-create feature
    """
    device = hd44780(serial, bitmode=8, gpio=gpio)
    serial.reset_mock()

    # Use canvas to create a screen worth of data
    with canvas(device) as drw:
        # Include unprintable character to show it gets ignored
        size = device.font.getsize('This is a test\uFFFF')
        drw.text(((80 - size[0]) // 2, 0), 'This is a test\uFFFF', font=device.font, fill='white')
        drw.rectangle((10, 10, 69, 14), fill='black', outline='white')
        drw.rectangle((10, 10, 49, 14), fill='white', outline='white')

    # Send DDRAMADDR and ascii for the line of text
    line1 = [call.command(0x81)] + \
        [call.data([0x54, 0x68, 0x69, 0x73, 0x20, 0x69, 0x73, 0x20, 0x61, 0x20, 0x74, 0x65, 0x73, 0x74])]

    # Create custom characters for the scrollbar
    custom = [call.command(0x40), call.data([0x00, 0x00, 0x1f, 0x1f, 0x1f, 0x1f, 0x1f, 0x00])] + \
        [call.command(0x48), call.data([0x00, 0x00, 0x1f, 0x00, 0x00, 0x00, 0x1f, 0x00])] + \
        [call.command(0x50), call.data([0x00, 0x00, 0x1f, 0x01, 0x01, 0x01, 0x1f, 0x00])]

    # Print the resulting custom characters to form the image of the scrollbar
    line2 = [call.command(0xc1), call.data([0x20, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x01, 0x01, 0x02, 0x20])]

    serial.assert_has_calls(line1 + custom + line2)


def test_custom_full():
    """
    Auto-create feature runs out of custom character space
    """
    device = hd44780(serial, bitmode=8, gpio=gpio)

    # Consume 8 special character positions
    img = Image.new('1', (80, 16), 0)
    drw = ImageDraw.Draw(img)
    for i in range(8):
        drw.rectangle((i * 5, 0, (i + 1) * 5, i), fill='white', outline='white')
    device.display(img)

    serial.reset_mock()

    # Consume one more (on the last char position on screen)
    drw.line((75, 8, 79, 15), fill='white')
    device.display(img)

    serial.assert_has_calls([call.command(0xcf), call.data([0x5f])])


def test_get_font():
    """
    Test get font capability by requesting two fonts and printing a single
    character from each that will be different between the two fonts
    """
    device = hd44780(serial, bitmode=8, gpio=gpio)

    img = Image.new('1', (10, 8), 0)
    a00 = device.get_font(0)
    a02 = device.get_font(1)
    drw = ImageDraw.Draw(img)

    assert a00.getsize('\u00E0') == (5, 8)

    drw.text((0, 0), '\u00E0', font=a00, fill='white')
    drw.text((5, 0), '\u00E0', font=a02, fill='white')

    assert img.tobytes() == \
        b'\x02\x00\x01\x00H\x00\xab\x80\x90@\x93\xc0l@\x03\xc0'


def test_no_contrast():
    """
    HD44780 should ignore requests to change contrast
    """
    device = hd44780(serial, bitmode=8, gpio=gpio)
    device.contrast(100)


def test_i2c_backlight():
    """
    Test of i2c_backlight
    """

    def _mask(pin):
        """
        Return a mask that contains a 1 in the pin position
        """
        return 1 << pin

    serial = Mock(unsafe=True, _bitmode=4, _backlight_enabled=0, _mask=_mask)
    hd44780(serial, bitmode=8, backpack_pin=3, gpio=gpio)

    assert serial._backlight_enabled == 8


def test_i2c_does_not_support_backlight():
    """
    An exception is thrown if supplied serial_interface does not support a backlight
    """
    import luma.core
    serial = Mock(spec_set=luma.core.interface.serial.i2c)
    flag = False
    try:
        hd44780(serial, gpio=gpio, backpack_pin=3)
    except luma.core.error.UnsupportedPlatform as ex:
        assert str(ex) == "This I2C interface does not support a backlight"
        flag = True

    assert flag, "Expected exception but none occured"


def test_unsupported_display_mode():
    """
    An exception is thrown if an unsupported display mode is requested
    """
    import luma.core
    try:
        hd44780(serial, width=12, height=3, gpio=gpio)
    except luma.core.error.DeviceDisplayModeError as ex:
        assert str(ex) == "Unsupported display mode: 12 x 3"
