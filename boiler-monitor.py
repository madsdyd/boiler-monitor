# Python program for detection of a specific color using OpenCV with Python
# Code lifted from: https://www.geeksforgeeks.org/detection-specific-colorblue-using-opencv-python/
# and, from https://docs.opencv.org/3.4.15/da/d97/tutorial_threshold_inRange.html
# And lots of other places!
# Not lifted code is by me, https://github.com/madsdyd
import cv2
import numpy as np

import coloredlogs
import logging
import time
import datetime

import paramiko
import sys
import subprocess

import argparse
import serial
import traceback

# Set up logging
logger = logging.getLogger('boiler-monitor')
logger.setLevel(logging.DEBUG)
coloredlogs.install(level='DEBUG', fmt="[%(name)s] %(asctime)s %(levelname)s: %(message)s")


############################################################################################
def check_for_red(cap) -> bool:
    """Check for the presence of red in the image. Returns true, if red is found"""
    logger.debug("OCV: Capturing stuff")
    # Captures the live stream frame-by-frame
    _, frame = cap.read()
    logger.debug("OCV: Converting stuff")
    
    # Converts images from BGR to HSV
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    # lower_blue = np.array([110, 50, 50])
    # upper_blue = np.array([130, 255, 255])

    # These define the "cube" of the HSV colorspace to accept as read. Use the script
    # "inrange.py" to find the values that suits your case.
    lower_red = np.array([130, 70, 70])
    upper_red = np.array([180, 255, 255])
    
    logger.debug("OCV: Creating mask")
    
    # Here we are defining range of red color in HSV
    # This creates a mask of red coloured
    # objects found in the frame.
    mask = cv2.inRange(hsv, lower_red, upper_red)

    # Add noise removal to mask
    # https://techvidvan.com/tutorials/detect-objects-of-similar-color-using-opencv-in-python/
    # define kernel size. Tune this to your lighting, etc.
    kernel = np.ones((4, 4), np.uint8)
    # Remove unnecessary noise from mask
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    # Find contours
    # https://dev.to/erol/object-detection-with-color-knl
    contours, _ = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # center = None

    logger.debug("OCV: Highlighting red")
    
    # The bitwise and of the frame and mask is done so
    # that only the red coloured objects are highlighted
    # and stored in res
    res = cv2.bitwise_and(frame, frame, mask=mask)

    # Highlight largest contour on res, if present
    # get max contour
    if len(contours) > 0:
        c = max(contours, key=cv2.contourArea)

        # Get smallest rectangle with max contour
        rect = cv2.minAreaRect(c)

        # Draw it
        ((x, y), (width, height), rotation) = rect
        s = f"x {np.round(x)}, y: {np.round(y)}, width: {np.round(width)}, height: {np.round(height)}, rotation: {np.round(rotation)}"
        # box
        box = cv2.boxPoints(rect)
        box = np.int64(box)

        # moment
        m = cv2.moments(c)
        if m["m00"] > 0:
            center = (int(m["m10"] / m["m00"]), int(m["m01"] / m["m00"]))

            # point in center
            cv2.circle(res, center, 5, (255, 0, 255), -1)

            # draw contour
            cv2.drawContours(res, [box], 0, (0, 255, 255), 2)

            # logger.debug inform
            cv2.putText(res, s, (25, 50), cv2.FONT_HERSHEY_COMPLEX_SMALL, 1, (255, 255, 255), 2)

    logger.debug("OCV: Showing images")
    # This displays the frame, mask
    # and res which we created in 3 separate windows.
    cv2.imshow('frame', frame)
    cv2.imshow('mask', mask)
    cv2.imshow('res', res)

    # True if we found red
    return len(contours) > 0


##################################################################################
# Some really shady state management
# Assume boiler OK on start
boiler_ok = True
# Set to time for boiler fail (set using arguments, later)
boiler_failed_time = None
last_red_seen = None
# Assume we did not send a notification / log something
notification_sent = False

# If red not seen for this long, assume boiler OK
red_timeout_time = datetime.timedelta(seconds=1)

# Controls the recover of the boiler
# Initialized to avoid warnings in intellij
boiler_recover_delay = datetime.timedelta(seconds=1)
boiler_next_recover_time = datetime.datetime.now()

# config for notifications
ssh_host = ''
ssh_username = ''
notification_mail_address = ''

#################################################################################


# serial
# This blocks, which sucks.
def run_servo(port: str, min_value: bytes, max_value: bytes) -> bool:
    """This runs the servo, which trigger the button on the boiler.
    If unable to open the serial port, an error is logged, then the process continues.
    :return True if run to completion, False otherwise"""
    logger.debug("Running servo")
    ser = None
    try:
        ser = serial.Serial(port, 9600)
    except Exception as e:
        logging.error(traceback.format_exc())
        logger.error("Unable to open serial port" + port)
        return False
    if ser:
        logger.info("Allowing serial port to settle")
        time.sleep(1)
        ser.write(min_value)
        logger.info("Min value sent")
        time.sleep(2)
        ser.write(max_value)
        logger.info("Max value sent")
        time.sleep(2)
        ser.write(min_value)
        logger.info("Min value sent")
        time.sleep(2)
        logger.info("Closing serial port")
        ser.close()
        logger.info("Serial control for button sent")
        return True
    else:
        logger.warning("Unable to open serial port" + port)
        return False


def run_ssh_cmd(cmd: str) -> bool:
    """Run a command through ssh
    :param cmd: The command to run
    :return: If the command was a success or not
    """
    logger.info("Running ssh cmd: " + cmd)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ssh_host, username=ssh_username)
    stdin, stdout, stderr = client.exec_command(cmd)
    call_ok = stdout.channel.recv_exit_status()
    if 0 != call_ok:
        logger.error("Problem sending notification on ssh. Exit code: " + str(call_ok))
        stdout = stdout.readlines()
        stderr = stderr.readlines()
        logger.error("stdout:\n" + "\n".join(stdout))
        logger.error("stderr:\n" + "\n".join(stderr))
    client.close()
    return 0 == call_ok


def run_shell_cmd(cmd: str) -> bool:
    """
    Run a shell command
    :param cmd: The command to run
    :return: If the command was a success or not
    """
    logger.info("Running local cmd: " + cmd)
    returned_value = subprocess.call(cmd, shell=True)
    return 0 == returned_value


def boiler_notification_send(prod: bool, state: str) -> None:
    """
    Send a notification, if in prod mode, with the state passed as parameter.
    :param prod: Set to True if in production mode. If not set to true, won't actually send a notification.
    :param state: The state of the boiler, typically FAIL or OK
    """
    cmd = "echo 'Boiler " + state + "' | mail -s \"Boiler " + state + " at $(date)\" " + notification_mail_address
    notification_sent_ok = False
    if prod:
        if ssh_host and ssh_username and notification_mail_address:
            logger.info("Using ssh for sending notification")
            notification_sent_ok = run_ssh_cmd(cmd)
        else:
            if notification_mail_address:
                logger.info("Using local host for sending notification")
                notification_sent_ok = run_shell_cmd(cmd)
            else:
                # The user was already told that the mail adress is missing
                return
    else:
        logger.info("Not PROD mode, Boiler " + state + " notification NOT sent")
        return
    if notification_sent_ok:
        logger.info("Boiler " + state + " notification sent")
    else:
        logger.info("Boiler " + state + " notification NOT sent, due to some error")


def boiler_failed(prod):
    """Call this to send a notification, whenever the boiler fails.
    :param prod: Set to True if in production mode. If not set to true, won't actually send a notification."""
    boiler_notification_send(prod, "FAIL")


def boiler_button_pressed(prod):
    """Call this to send a notification, whenever the reset button on the boiler is pressed.
    :param prod: Set to True if in production mode. If not set to true, won't actually send a notification."""
    boiler_notification_send(prod, "BUTTON_PRESS")


def boiler_button_pressed_failed(prod):
    """Call this to send a notification, whenever the reset button on the boiler failed to be pressed
    :param prod: Set to True if in production mode. If not set to true, won't actually send a notification."""
    boiler_notification_send(prod, "BUTTON_PRESS_FAILED_ERROR")


# Call this, if boiler recovered
def boiler_recovered(prod):
    """Call this to send a notification, whenever the boiler recovers from a failure state.
    :param prod: Set to True if in production mode. If not set to true, won't actually send a notification."""
    boiler_notification_send(prod, "OK")


def check_red_timeout(prod: bool):
    """ Check if a long enough time have passed since we last saw a red light.
    If enough time have passed, set boiler state to OK, and trigger an OK notification.
    :param prod: Set to True if in production mode"""
    global last_red_seen
    global boiler_ok
    global red_timeout_time
    if not boiler_ok:
        logger.debug("Boiler not ok, check red timeout")
        now = datetime.datetime.now()
        if last_red_seen + red_timeout_time < now:
            logger.info("Boiler timeout reached, boiler is OK")
            boiler_ok = True
            boiler_recovered(prod)
        else:
            logger.debug("Waiting for timeout on red")


def handle_red_seen(prod: bool):
    """Call this, when a red color has been seen.
    If the boiler state is currently OK, fail it, send a notification, and set up for recovery.
    Could add some more sophisticated detection, such as x failure event in time window of n seconds,
    but in practice this seems to work well, so no need to overcomplicate it.
    :param prod: Set to True if in production mode"""
    global last_red_seen
    global boiler_ok
    global boiler_failed_time
    global red_timeout_time
    global boiler_next_recover_time
    global boiler_recover_delay
    last_red_seen = datetime.datetime.now()
    if boiler_ok:
        boiler_ok = False
        logger.error("Boiler failed, sending notification. If no red seen for " + str(red_timeout_time) +
                     " will assume boiler OK")
        # Set up for recover check
        boiler_failed_time = datetime.datetime.now()
        boiler_next_recover_time = boiler_failed_time + boiler_recover_delay
        logger.info("Will try to recover boiler at " + str(boiler_next_recover_time))
        # Send notification of failure
        boiler_failed(prod)


################################################################################
# PARSE ARGS
################################################################################
def get_args() -> argparse.Namespace:
    """
    Parse arguments
    :return: The parsed arguments.
    """
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-d", "--debug", action="store_true",
                        help="Output extra debug information. Note, lots of output.")
    # Required unless user is asking for the effective config
    parser.add_argument("-p", "--prod", action="store_true",
                        help="Production mode. Enable notifications.")
    parser.add_argument("-c", "--camera", default=0,
                        help="What camera to use [0]")
    parser.add_argument("-s", "--serial-port", default="/dev/ttyACM0",
                        help="Serial port servo [/dev/ttyACM0]")
    parser.add_argument("-e", "--delay", default=600,
                        help="Delay from failure until first button press, and between presses in seconds [600]")
    parser.add_argument("-r", "--red-timeout", default=20,
                        help="No red seen for this long => boiler recovered [20]")
    parser.add_argument("-t", "--trigger-finger", action="store_true",
                        help="Trigger the finger, then exit")
    parser.add_argument("-o", "--ssh-host", default="",
                        help="ssh host to use for sending mails []. If empty, try to send mails directly.")
    parser.add_argument("-u", "--ssh-user", default="",
                        help="ssh user to use for sending mails []. If empty, try to send mails directly.")
    parser.add_argument("-m", "--mail-address", default="",
                        help="Mail address for sending notifications []. If empty no notifications are sent.")
    parser.description = "Monitor boiler, send mail when state changes between failure and OK"
    parser.epilog = """
Examples:
    Run with camera 2 in production mode
    """ + sys.argv[0] + """ --camera 2 --prod

"""
    args = parser.parse_args()
    return args


################################################################################
# MAIN
################################################################################
def main():

    # At some point, I should learn Python OOP....
    global boiler_recover_delay
    global boiler_next_recover_time
    global boiler_failed_time
    global red_timeout_time
    global ssh_host
    global ssh_username
    global notification_mail_address

    # Constants for min and max servo values
    min_value = b"120\n"
    max_value = b"30\n"

    # Get args, configure
    args = get_args()

    if args.debug:
        logger.debug("cli options:")
        logger.debug("  debug: " + str(args.debug))
        logger.debug("  prod: " + str(args.prod))
        logger.debug("  camera: " + str(args.camera))
        logger.debug("  serial-port: " + str(args.serial_port))
        logger.debug("  delay: " + str(args.delay))
        logger.debug("  red-timeout: " + str(args.red_timeout))
        logger.debug("  trigger-finger: " + str(args.trigger_finger))
        logger.debug("  ssh-host: " + str(args.ssh_host))
        logger.debug("  ssh-user: " + str(args.ssh_user))
        logger.debug("  mail-address: " + str(args.mail_address))
    else:
        # Disable debug for now
        logging.disable(logging.DEBUG)

    # If the user wanted to test the trigger-finger, the run it, and exit.
    if args.trigger_finger:
        logger.info("Triggering finger")
        run_servo(args.serial_port, min_value, max_value)
        sys.exit()

    # set args from values

    camera = int(args.camera)
    prod = args.prod
    boiler_recover_delay = datetime.timedelta(seconds=int(args.delay))
    red_timeout_time = datetime.timedelta(seconds=int(args.red_timeout))
    ssh_host = args.ssh_host
    ssh_username = args.ssh_user
    notification_mail_address = args.mail_address

    if "" == notification_mail_address:
        logger.warning("--mail-address not set, not sending any notifications")

    # Setting up OpenCV
    # Webcamera is used to capture the frames
    cap = cv2.VideoCapture(camera)

    logger.info("Starting boiler monitor. Boiler starts in OK state")

    while True:

        try:
            logger.debug("Boiler status: " + str(boiler_ok))
            red_present = check_for_red(cap)
            logger.debug("Red present: " + str(red_present))

            # If we see something red, fail the boiler
            if red_present:
                handle_red_seen(prod)
            else:
                # If not, check if we reach our grace period of no red seen
                check_red_timeout(prod)

            # If the boiler is currently failed, check if we should try to restart it
            if not boiler_ok:
                if datetime.datetime.now() > boiler_next_recover_time:
                    logger.info("Trying to recover boiler by pressing button")
                    if run_servo(args.serial_port, min_value, max_value):
                        boiler_button_pressed(prod)
                    else:
                        boiler_button_pressed_failed(prod)
                    # If this does not work, try again later
                    boiler_next_recover_time = boiler_next_recover_time + boiler_recover_delay
                    logger.info("If boiler does not recover: Will try to recover boiler at " +
                                str(boiler_next_recover_time))

            logger.debug("Checking for input, that can stop the program")
            k = cv2.waitKey(5) & 0xFF
            if k == 27:
                break

            # sleep a bit to avoid flooding stuff
            time.sleep(0.095)
        except Exception as e:
            logging.error(traceback.format_exc())
            logging.error("Sleeping 10 seconds, to normalize system")
            time.sleep(10)
            logging.info("Restarting monitoring")

    # Destroys all of the HighGUI windows.
    cv2.destroyAllWindows()

    # release the captured frame
    cap.release()


main()
    
