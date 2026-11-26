import unittest

from PIL import Image, ImageDraw

import logocolor as LC


def logo(bg, accents):
    im = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((0, 0, 119, 119), fill=bg)
    for box, col in accents:
        d.rectangle(box, fill=col)
    return im


class LogoColor(unittest.TestCase):
    def test_red_and_black_logo_is_red(self):
        h = LC.hue_of_image(logo((255, 255, 255, 255), [((20, 30, 100, 80), (200, 40, 50, 255)), ((10, 85, 110, 110), (10, 10, 10, 255))]))
        self.assertTrue(h >= 345 or h <= 10, h)

    def test_gray_circle_with_light_blue_accent_is_blue(self):
        h = LC.hue_of_image(logo((185, 185, 185, 255), [((10, 50, 110, 75), (130, 205, 225, 255))]))
        self.assertTrue(185 <= h <= 205, h)

    def test_all_gray_has_no_color(self):
        self.assertIsNone(LC.hue_of_image(logo((150, 150, 150, 255), [])))


if __name__ == "__main__":
    unittest.main()
