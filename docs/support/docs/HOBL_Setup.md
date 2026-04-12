# Setup

## Lab Setup
* The HOBL UI software allows controlling multiple DUTs from a single Host, so a lab will generally have a single HOBL host computer.  
* The HOBL UI is a web server that can be accessed by multiple users simultaneously, if needed.  For larger labs, it can also be executed with IIS.
* The Hosts and DUTs should be on a local network that has internet access.
* The host should be connected with ethernet, but the DUT should be on Wi-Fi, to be representative of a user operating a device on battery.  Ethernet dongles often prevent devices from getting to lower power states.
* The Wi-Fi network should be set up to provide each device with **50 Mbps**, again for representativeness.  Significantly more or less BW has power consumption impact.  Not all AP's are good at controlling this, but we have found the HPE Aruba line of access points adept at it.  50 Mbps is also the minimum bandwidth requirement for correct functionality.
* 5 GHz channels should be used for connecting to DUTs.
* Do not domain-join the DUTs.
* Corporate network traffic can be intense, so it is recommended to deploy a firewall between the lab LAN and corporate networks that will filter out corporate traffic but still allow access to the internet.  This will improve representativeness and reduce test variability.
* HOBL supports automatic recharging of DUTs via a variety of mechanisms, as long as they can be controlled by a shell command.  The commands are specified in the charge_on and charge_off sections of the Device Profile.  The most common mechanisms are:
    1. A Raritan PX-series IP-addressable power strip
    1. <a href="https://dlidirect.com/products/new-pro-switch" target="_blank">Digital-Loggers Pro Switch</a>
    1. An iBoot controlled by either ethernet or relay.  
* A luminance meter should be used to determine the DUT brightness setting that corresponds to 150 nits.  Measure and average all 4 counters plus center of a pure white screen.  All tests are expected to run at this brightness except JEITA-related tests (which are at 200 nits).  A nits map should be specified in the profile to associate the appropriate slider postiions to 150 and 200 nits respectively.  <TODO: Add section on profle setup and tools>
* Tests are run with audio volume set to the out-of-box default level.  To ensure consistency, once this value is determined, it should also be specified in the device profile.

## Account Setup
The following accounts need to be created for the DUT:

1. <a href="https://outlook.live.com/owa/" target="_blank">MSA (Microsoft Account)</a> for logging into Windows, Teams, OneDrive, Office, and the Store.  Each DUT needs its own account, otherwise files syncing across devices will not only cause variability but can break tests.  It is critical to set security for the account, otherwise it will require a phone number from you in about a week.  To secure the account, go to <a href="https://account.microsoft.com" target="_blank">https://account.microsoft.com</a> and sign in with the newly created MSA.  Then select the "Security" menu item at the top.  Then click "Get Started" on the "Advanced Security Options" card.  Select to add a verification email account (so that you don't have to use a phone number), then you will be prompted to send verification codes twice.  You can use the same verification account for all MSA's that you create.  Log into the verification account using a different web browser or computer (so you don't log out of your MSA), to retrieve the codes.  Be sure to NOT set 2FA (MFA) in order to get full automation.

1. Office - To run scenarios that involve Microsoft OFfice (i.e. productivity, abl_active) you will need to purchase a subscription to Microsft 365 Personal or Family (not Business), otherwise you will only have a 5-day grace period for testing after install.  The subscription needs to be tied to the MSA.  There is a limit to how many devices can use a single m365 subscription, so you may need to release the subscription on devices no longer used.  This can be managed at
<a href="https://account.microsoft.com/services/office/install" target="_blank">https://account.microsoft.com/services/office/install</a>.  Click "Sign out of Office" on devices no longer being used.  You may also have to do this for prior OS images on an active DUT, since new OS images may be considered a different "device".

1. Teams - The MSA account needs to be one-time associated with a Teams Organization set up for testing.  Also make sure it's only associated with one organization, otherwise the DUT will prompt for which Org to execute with, which will break the automation.  The Teams org can be shared across any number of MSA's, so generally only one Teams org needs to be set up per test house.  Once the org is set up, you assocociate the MSA by clicking the provided URL and entering the MSA email.
    * Creating a Teams Test Organization:

        1. Go to MS Teams Page:  <a href="https://www.microsoft.com/en-us/microsoft-365/microsoft-teams/group-chat-software" target="_blank">https://www.microsoft.com/en-us/microsoft-365/microsoft-teams/group-chat-software</a>
        2.	Click Sign up for Free:  <a href="https://go.microsoft.com/fwlink/p/?LinkID=2123761&clcid=0x409&culture=en-us&country=US&lm=deeplink&lmsrc=homePageWeb&cmpid=FreemiumSignUpHero" target="_blank">https://go.microsoft.com/fwlink/p/?LinkID=2123761&clcid=0x409&culture=en-us&country=US&lm=deeplink&lmsrc=homePageWeb&cmpid=FreemiumSignUpHero</a>
        3.	Enter Email info and continue with sign up.
        4.	Select “For work and organizations” or “Not a school organization” depending on which prompt you get.
        5.	Enter a Test Company Name (ex. “Test Company”, “Contoso”, “Teams Testing”, etc.).
        6.	Click Create Teams Org.
        7.	Continue to the Web Teams site.
        8.	Wait for Teams org to finish creation and the web Teams site to finish loading.
        9.	Once the page has loaded, click on the user account icon in the top right of the page.
        10.	Select “Manage Org” from the dropdown .
        11.	Click the Settings tab in the top middle of the page.
        12.	Expand the “Manage Link” Section.
        13.	Check the toggle to “Enable link”.
        14.	Check the toggle to “Enable auto-join”.
        15. The Link URL below the toggles can now be used by any test account to join the new test org. 

1. <a href="https://www.netflix.com/signup" target="_blank">Netflix Premium</a> for the Netflix scenario.  Up to 4 DUTs can be used with the same account.

## Host Setup
The host computer houses the HOBL test framework and UI.  Through this, users execute tests remotely on one or more DUTs, and view the results.

Host computer system requirements are:  Intel or AMD processor running Windows 11.  For large labs, factor approximately 1 host core per 10 devices, and 16 GB of RAM + (0.5 GB * number of DUTs).

1. Make sure Git is intalled on your Host computer.
1. Clone the HOBL repo to your preferred location, but note that putting it at "c:\hobl" will simplify things.  You might want to do a shallow clone if your organization has download capacity limits.
1. Run the host_setup.exe in the root folder.  This will:
    1. Download various items into the /Downloads folder.  These include:
        - The approipriate dut_setup executables.
        - ffmpeg.
        - Windows runtime libraries.
        - Set git hooks to automatically update the HOBL version on pulls.
        - Disable the Windows error reporting UI (to prevent halting automation in case of an error).
    1. Install embedded python.
    1. Download and install the HOBL UI in c:\HOBLweb.
        - If you installed hobl in a folder other than "c:\hobl", then you need to hand-edit c:\hoblweb\appsettings.json and modify the "DocsPath" paramter accordingly.
        - Likewise, if you intend to have your results go to a different base folder than "c:\hobl_results", modify the "ResultsPath" parameter accordingly.  Make sure that the "results_dir" parameter in your profile includes this base path.

To get future updates to the HOBL source code, do a "git pull" in the hobl folder.  To get future updates to the HOBL UI, rerun host_setup.exe and just select "HOBL User Interface" item.

HOBLweb UI documentation can be found here: [HOBL UI](HOBL_UI.md)

Set up a Device Profile for each DUT in the HOBLweb UI, giving it a unique name (typically we name it the name of the DUT), and modifying the parameters as appropriate.  Use the Parameters documentation as a guide.

## DUT Setup For Windows
1. After running host_setup.exe, dut_setup.exe should be found in the /downloads/Setup folder.  Copy dut_setup_\<ver\>.exe from here to a USB stick.
1. Plug the USB stick into the DUT and execute dut_setup.exe. This will install SimpleRemote and configure the DUT for communication with the HOBL Host.  HOBL can't communicate without this, and you will see errors about failed remote directory creation and communication timeouts.
1. You will be prompted to change the name of the device if desired.  Click Next.
1. You will be prompted to enter Wi-Fi information.  This will be saved to the USB stick so that you can set up the device again in the future, or other devices in the lab, without having to re-enter the information.
    1. This will setup various registry settings and launch simple_remote to allow communication from the host.
    1. If you see an error when it tries to set the developer mode, this can safely be ignored.
4. Test network connection to the DUT:
    1. Host and DUT need to be on the same subnet (first 2 octets of the IP address).
    1. Run Cmd or Powershell on the Host.
    1. Make sure sure DUT responds to pings:  `ping <dut_ip>`
    1. Make sure DUT can ping host as well.
    1. Run the "comm_check" scenario to make sure that all communications needs are met.

## DUT Setup For macOS
1. Manually make sure the device is onnected to the appropriate Wi-Fi netowrk, on the same subnet as the Host.
1. After running host_setup.exe, dut_setup.sh should be found in the /downloads/Setup folder.  Copy dut_setup.sh from here to a USB stick.
1. Plug the USB stick into the DUT and execute dut_setup.sh.
1. There will be numerous prompts for password and to enable various security items.  It's critical to enable all.
1. Test network connection to the DUT:
    1. Host and DUT need to be on the same subnet (first 2 octets of the IP address).
    1. Run Cmd or Powershell on the Host.
    1. Make sure sure DUT responds to pings:  `ping <dut_ip>`
    1. Make sure DUT can ping host as well.
    1. Run the "comm_check" scenario to make sure that all communications needs are met.
