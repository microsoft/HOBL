# Design Philosophy

## Key principles:

### Representativeness

HOBL's main purpose is for computer system validation and tuning.  There are subtle but critical differences between synthetic benchmarks and how users really use devices.  These differences can result in wrong tuning choices and missed bugs.  In order to bring impact to real users, HOBL aims to interact with devices the way real users do, and craft test scenarios based on telemetry and user research.  For example, in the "web" scenario, these aspects are based on telemetry and user research studies of the typical user:

  - Which websites to visit
  - How many tabs to open
  - How much time to spend on each site
  - Scrolling behavior
  - New Tab Page visits
  - Typing rate
  - Browser caching behavior
  - And so on...

### Usability

Ease of setup/use is critical so that users can focus on studies rather than infrastructure.  Usability features in HOBL include:

* Stand-alone UI app or centralized lab website.
* Ability to manage stations, create test plans, execute jobs, monitor status, analyze results, Remote to device, etc.
* HOBL UI website can be accessed from corp/internet networks, no need for users to be in the lab.
* Remote to DUT directly within HOBL UI.
* Support for streaming video and recordings - RTSP or USB cams, screen casts from DUT.

### Extensibility

* Can control or be controlled by other automation.
* Plug-and-play tools:
    * Add a tool by dropping it in the “tools” folder.
    * Callback architecture allows actions at specific phases of test flow.
    * Interface custom DAQs, thermal chambers, chargers, and other equipment.
* Scenario Maker app:
    * Quickly and easily create tests by recording actions.
    * Democratizes test creation, relieving bottlenecks.

### Scalability

Ability to run locally on a device:

  * valuable for devs to reproduce issues.

Ability run on a centralized server controlling hundreds of devices:

  * Maximizes electrical and physical capacity for DUTs.
  * External equipment not required.
  * Allows full end-to-end automation, including re-imaging, rebooting, real-time monitoring, etc.

### Capability

* Ability to test major platforms - Windows, Win365, MacOS, Android.
* Ability to interact with Games.
* Data analysis features.

### Controllability

To measure nuances in power and performance:

  * All variables need to be controlled tightly.
  * Tests need to do the exact same thing, with same timing, every time.  In HOBL all action timing is with reference to the beginning of the scenario, so that timing errors don't accumulate over time.

Web Replay technology:

  * Recorded web sites eliminates variability of live web pages.
  * Same content and timing, every time.
  * Prevents getting bot-detected by web sites.
  * Prevents need for creating accounts and logging into web sites.

## How we automate and why:

There are numerous ways to automate interactivity with a computer system, with various pros and cons.  HOBL actually combines a number of them:

For changing system settings and preparing the device, setting registry keys and other command-line operations is preferred for simplicity and reliability.  If that's not viable, then we'll use UI automation using Selenium-based Windows Application Driver (which leverages the accessibility tags for elements in Windows), for its versatility.

For test scenarios that are actually measuring power or performance, the big challenge is we need to make sure the automation mechanism itself doesn't consume noticeable CPU utilization, and that it's representative of how a real user would interact with the device.  Windows Application Driver can consume a significant amount of CPU cycles, and direct application API calls or command-line execution aren't representative of how most users operate.  When bugs were found with these methods in the past, they would get deprioritized or rejected due to, "we don't expect users to do this".  As a result, we ensure that measured scenarios use keystrokes and mouse movement/clicks injected at the HID level, same as where a keyboard or mouse driver would interface.  The trick then, is to determine where to click the mouse.  For this we use an image-recognition based system using strategic screenshots.  On the device, we only capture an area of the screen where we expect the desired element to be, then, on the host, we search the capture for the precise location of the element, find it's relative coordinates, and send a mouse click command at those coordinates.  We've found that we've been able to automate scenarios quite well by capturing small enough regions infrequently enough that we don't see any noticeable impact to power consumption.  Scenario Maker is an included application that makes it easy to create test scenarios using this automation mechanism.

To handle different themes and colors, we convert images to black-and-white outlines, via edge detection.  To handle different screen resolutions and scaling factors, we read those factors from the DUT and scale the template accordingly before matching.  We can also store multiple templates for matching, and can override matching and edge-detection thresholds as needed.  This gives us a lot of knobs creating a robust system.

## Why Python?

No compiling.  This results in:

  * Faster fixes and feature development
  * Incorporating fixes without disturbing currently running test.  These is crucial for large deployments and long-running studies managed by a centralized host.

Powerful, yet easy to read

  * Novice users can apply emergency fixes and work-arounds.
  * External teams can easily develop their own tools and scenarios.

## Why Git for updates?

Again, the key is to incorporate fixes and updates without disturbing current running tests.  A "git pull" will only update the python files needed.  Also, even if a python file was loaded for a current test, it can still be replaced by an update with disturbing the test.  Whereas a compiled executable test would need to be stopped for it to be updated.