import cv2
import os
import numpy as np
import datetime

from astral import LocationInfo
from astral.sun import sun
from time import sleep
from gi.repository import Gio


def get_laptop_dark_light_mode():
    settings = Gio.Settings.new("org.gnome.desktop.interface")
    mode = settings.get_string("color-scheme")
    return mode


def set_dark_mode():
    settings = Gio.Settings.new("org.gnome.desktop.interface")
    settings.set_string("color-scheme", "prefer-dark")


def set_light_mode():
    settings = Gio.Settings.new("org.gnome.desktop.interface")
    settings.set_string("color-scheme", "default")


def read_picture():
    cam = cv2.VideoCapture(0)
    result, image = cam.read()
    cam.release()
    return image


def crop_center_picture(image):
    width = image.shape[1]
    height = image.shape[0]
    cropped_image = image[0:height, int(width/3):int(width*2/3)]
    return cropped_image


def crop_left_picture(image):
    width = image.shape[1]
    height = image.shape[0]
    cropped_image = image[0:height, 0:int(width/3)]
    return cropped_image


def crop_right_picture(image):
    width = image.shape[1]
    height = image.shape[0]
    cropped_image = image[0:height, int(width*2/3):int(width)]
    return cropped_image


def return_brigthness_scale(image):
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mean = np.mean(grey)
    standard_deviation = np.std(grey)
    return mean, standard_deviation


def calibration_measure2display(
        measured_brightness,
        standard_deviation,
        multipliers
):
    brightness = measured_brightness/255*9.63
    brightness_correction = standard_deviation/255*9.63

    brightness = pow(brightness, 2)
    brightness_correction = pow(brightness_correction, 2)

    # print("Light amount: " + str(int(brightness)) + r"/93")
    # print("Light st.dev: " + str(int(brightness_correction)))

    if 1 <= brightness < 2:
        brightness = 0
    elif 2 <= brightness < 5:
        brightness = 2 + brightness_correction * multipliers[0]
    elif 5 <= brightness < 15:
        brightness = int(brightness * multipliers[1] + brightness_correction/2)
    elif 15 <= brightness < 30:
        brightness = int(brightness * multipliers[2] + brightness_correction/3)
    elif 30 <= brightness < 45:
        brightness = int(brightness * multipliers[3] + brightness_correction/3)
    elif 45 <= brightness < 60:
        brightness = int(brightness * multipliers[4] + brightness_correction/4)
    elif 60 <= brightness < 75:
        brightness = int(brightness * multipliers[5] + brightness_correction/2)
    elif 75 <= brightness < 85:
        brightness = int(brightness * multipliers[6] + brightness_correction/2)
    elif 85 <= brightness < 90:
        brightness = int(brightness * multipliers[7] + brightness_correction)
    elif 90 <= brightness < 93:
        brightness = 93

    if brightness <= 0:
        brightness = 0
    elif brightness > 93:
        brightness = 93
    return int(brightness)


def get_brightness():
    f = open(r"/sys/class/backlight/intel_backlight/brightness")
    value = f.read()
    value_int = [int(s) for s in value.split() if s.isdigit()][0]
    f.close()
    return value_int


def set_brightness(display_brightness_input):
    value_int = get_brightness()
    if display_brightness_input > value_int:
        for i in range(value_int, display_brightness_input, 1):
            cmd = ("sudo su -c 'echo " + str(int(i)) + " > /sys/class/backlight/intel_backlight/brightness'")
            status = os.system(cmd)
            sleep(0.02)
    elif display_brightness_input < value_int:
        for i in range(value_int, display_brightness_input, -1):
            cmd = ("sudo su -c 'echo " + str(int(i)) + " > /sys/class/backlight/intel_backlight/brightness'")
            status = os.system(cmd)
            sleep(0.02)


def find_sunset_sunrise():
    city = LocationInfo('Brussels', 'Belgium', 'Europe/Brussels', 50.83, 4.39)
    s = sun(city.observer, date=datetime.datetime.today())

    sunrise_h = s["sunrise"].hour
    sunrise_m = s["sunrise"].minute
    sunset_h = s["sunset"].hour
    sunset_m = s["sunset"].minute
    return \
        sunrise_h, \
        sunrise_m, \
        sunset_h, \
        sunset_m,


def define_multipliers(
        measured_face_brightness,
        measured_left_brightness,
        measured_right_brightness,
        laptop_color_mode,
):
    diffusion_constant = 10
    multipliers_light = [1.2, 1.35, 1.44, 1.7, 2, 1.5, 1.2, 1]
    multipliers_dark = [1, 1, 1, 1, 1, 1, 1, 1]
    multipliers_mid_high = list(np.array(multipliers_dark)*1/3 + np.array(multipliers_light)*2/3)
    multipliers_mid_low = list(np.array(multipliers_dark)*2/3+np.array(multipliers_light)*1/3)
    if measured_face_brightness - (measured_left_brightness + measured_right_brightness) / 2 > diffusion_constant:
        # luce di fronte a utente
        light_front = True
        light_rear = False
    elif measured_face_brightness - (measured_left_brightness + measured_right_brightness) / 2 < -diffusion_constant:
        light_front = False
        light_rear = True
    else:
        light_front = False
        light_rear = False

    # day = True
    # night = False

    if laptop_color_mode == 'default':
        dark_mode = False
    elif laptop_color_mode == 'prefer-dark':
        dark_mode = True
    # TODO check all conditions below
    if light_front and not dark_mode:
        #voglio tanta luce
        multipliers = multipliers_light
    elif not light_front and not light_rear and dark_mode:
        # voglio scuro
        multipliers = multipliers_dark
    elif light_rear and dark_mode:
        # mezza via piu alta
        multipliers = multipliers_mid_high
    elif light_rear and not dark_mode:
        # mezza via piu bassa
        multipliers = multipliers_mid_low
    else:
        multipliers = multipliers_mid_high
    # print(multipliers)
    return multipliers


def main(
        set_display_brightness=True,
):
    laptop_color_mode = get_laptop_dark_light_mode()
    image = read_picture()
    cropped_center_image = crop_center_picture(image)
    cropped_left_image = crop_left_picture(image)
    cropped_right_image = crop_right_picture(image)

    measured_face_brightness, face_standard_deviation = return_brigthness_scale(cropped_center_image)
    measured_left_brightness, left_standard_deviation = return_brigthness_scale(cropped_left_image)
    measured_right_brightness, right_standard_deviation = return_brigthness_scale(cropped_right_image)

    multipliers = define_multipliers(
        measured_face_brightness,
        measured_left_brightness,
        measured_right_brightness,
        laptop_color_mode,
    )

    face_to_background_deviation = abs((measured_face_brightness - measured_left_brightness) + (measured_face_brightness - measured_right_brightness))/2

    display_brightness_input = calibration_measure2display(measured_face_brightness, face_to_background_deviation, multipliers)
    if set_display_brightness:
        set_brightness(display_brightness_input)
    return display_brightness_input


if __name__ == '__main__':
    sleeping_time = 15
    while True:
        value_auto_set_before = get_brightness()
        value_auto_set_after = main(set_display_brightness=False)
        delta_brightness = int(value_auto_set_before - value_auto_set_after)

        if value_auto_set_after <= 3:
            delta_lim = 1
        else:
            delta_lim = 11

        if abs(delta_brightness) < delta_lim:
            set_display_brightness = False
        else:
            set_display_brightness = True
        value_auto_set_after = main(set_display_brightness)
        print(value_auto_set_after)
        if value_auto_set_after < 3:
            sleeping_time = 5
        else:
            sleeping_time = 2.5

        # if value_auto_set_after < 15:
        #     set_dark_mode()
        # else:
        #     set_light_mode()
        sleep(sleeping_time)

