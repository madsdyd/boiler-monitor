# boiler-monitor

This small collection of scripts, are used to monitor my boiler at home, and reset it on failure, while waiting to 
get the boiler replaced. 

The boiler will fail, and indicate this with a red LED coming on in the control panel. Whenever this happens, I need to press a 
button on the control panel, to reset the boiler. Problem is, it happens quite often, and we may 
have to wait weeks to get the boiler replaced. So, I wrote these scripts, that monitors the red LED, and presses
the reset button with a stick (after a delay/grace period), to reset the boiler.

## Reddit Post

I did a post about my solution in [Reddits "RedNeckEngineering" subreddit](https://www.reddit.com/r/redneckengineering/comments/qt5ejt/boiler_keeps_failing_no_problem_our_boiler_is/), and got 
some nice response. A couple of people asked for the source, so I decided to post it here. Check the post for a short video showing the system in action.

## Design constraints

A major constraint
was to be 100% non-intrusive in the boiler: No messing around with the electronics inside the boiler, 
for reasons I consider obvious.

Also, I wanted a quick solution, so was limited to use stuff I already had in my home. E.g. I had no
linear actuator, so I "build one" from an old wooden clothes hanger, some fixtures for electrical wire, 
some springs, and a tiny servo.

This is my first time using OpenCV, and I am also not well versed in Python, so please accept my apologies
for the errors and anti-patterns used in both. E.g. I can not be bothered to do OOP in Python, so there is that.

## System Architecture

Ok, that is probably a way to fancy heading, but some notes about the system, the following components are used:

* Laptop with webcam, running Linux (but I reckon anything that can run Python would be OK)
* An Arduino Uno to interface with the trigger arm (again, anything that can run a servo is probably OK)
* A small servo for moving the trigger arm (A Linear Actuator would probably be a better solution, alas, I did not have one such)
* A separate "server" for sending mail notifications, accessed using SSH. (Just the easiest way for me, as I was on a local area network with limited mail posibilities.)

If you just want to monitor, and get a notification, you obviously don't need the Arduino and servo.

If you do, in my setup, the Arduino is connected (and powered through) a serial port on the laptop, so that is how the laptop
assumes it can talk to the Arduino.

## Getting Started

The system was developed on Linux, but should work on any platform with Python support.

You will probably want to create a python dev/runtime environment, install the deps, and use those going forward.
This can be done like this:

```bash
python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt
```

Going forward, you will need to activate your python environment for every time you need to work the system. That is
run the second line above before messing around with the system: 

```bash
. venv/bin/activate
```

## Scripts

There are the following scripts and code files:

* [cams.py](cams.py) A small script to list the available cameras on your system. Note that this may not always works as expected, because it assumes consecutive camera numbers. On one of my systems, I have a camera 0 and a camera 2, but no 1. 
* [inrange.py](inrange.py) Lifted from the OpenCV documentation, use this to find (or tune) the color cube that your LED fail into.
* [boiler-monitor.py](boiler-monitor.py) This is actual script, that detects failures, trigger the trigger-arm, etc. Do run it with the `--help` option to get information about parameters, etc.
* [boiler-monitor.ino](boiler-monitor.ino) This is code for the Arduino. It is really, really simple: It reads an ascii string with an integer value from the serial port, and sets the position of the servo to the value. And thats all, really (then it loops, and waits for the next value).

## Example Sessions

### Creating the Python Environment

You only need to do this, the first time around, after cloning this repository into a suitable place:

```bash
$ python3 -m venv venv
$ . venv/bin/activate
(venv) $ pip install -r requirements.txt
Collecting bcrypt==3.2.0
...
Installing collected packages: pycparser, six, cffi, PyNaCl, numpy, humanfriendly, cryptography, bcrypt, paramiko, opencv-python, coloredlogs
Successfully installed PyNaCl-1.4.0 bcrypt-3.2.0 cffi-1.15.0 coloredlogs-15.0.1 cryptography-35.0.0 humanfriendly-10.0 numpy-1.21.4 opencv-python-4.5.3.56 paramiko-2.8.0 pycparser-2.21 six-1.16.0
```

### Running the boiler-monitor Script

You can run the boiler-monitor script like this (the first line is only needed if you have not already 
activated your Python environment)

```bash
$ . venv/bin/activate
(venv) $ python boiler-monitor.py --camera 0 --red-timeout 20 --delay 300 
[boiler-monitor] 2021-11-14 11:54:26 INFO: Starting boiler monitor. Boiler starts in OK state
[boiler-monitor] 2021-11-14 11:54:27 ERROR: Boiler failed, sending notification. If no red seen for 0:00:20 will assume boiler OK
[boiler-monitor] 2021-11-14 11:54:27 INFO: Will try to recover boiler at 2021-11-14 11:59:27.520772
[boiler-monitor] 2021-11-14 11:54:27 INFO: Not PROD mode, Boiler FAIL notification NOT sent
```

The example above starts the script, using the first (0) webcam in your system, with a timeout for the red LED of 20 seconds, and
with 300 seconds delay from seeing a failure until the trigger is pressed.

Note, the script opens three windows, where you can see:
* The raw image from the webcam (useful for pointing the webcam at the LED)
* The mask, which is a black/white image of where red was found
* The raw image with the mask applied and contours of the areas where red is found

Note, that you need to make sure that the only red that matches your HSV cube, is the LED. It was
easy for me, as the boiler is white, but if you have a boiler/something with a lot of red, you 
may need to add an "area of interest" to the OpenCV code. I don't really know how to do that, btw.

## Credits

"This code was written by comments from StackExchange"

I have tried to add comments with information about where I lifted the various bits and stuff. I assume most of the 
stuff I have copied is public domain. If you find some code in here that violates someones IP, please let me know,
and I will remove it.

Other code is by [me](https://github.com/madsdyd).

## License

You can use this under the GPL v3 license, and whatever it allows you to do, is fine with me.

## Disclaimer

It should be fairly obvious, that I take no responsibility for any use of these scripts, what so ever.
