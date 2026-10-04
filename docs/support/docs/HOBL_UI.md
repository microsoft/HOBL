# User Interface

## Installation

The HOBL UI is installed by selecting the "User Interface" option in host_setup.exe, found at the root of the repository.Installation will:
1. Download the latest HOBL UI archive from the GitHub releases and unpack it at c:\hoblweb.
1. Add a firewall rule to allow status updates to be pushed to it from clients.
1. Install a local SQL database and start it.
1. Attempt to launch the web app.

The default settings should work in most cases, but can be modified in c:\hoblweb\appsettings.json if not.  These include:
  * "DocsPath": "c:\\hobl\\docs\\support"
  * "ResultsPath": "C:\\hobl_results"

The web app needs to know where the documents are located and the base folder where results will be stored in order to display them properly.  It's imperative that any HOBL result_dir parameter specified for a run begin with the same path specified by "ResultPath".

If you want to make the web app available for remote access, you'll need to change the url from the default localhost to then name of the machine.  Do this by setting the HOBLWEB_URL environment variable like so: "http://host_name:80", where "host_name" is the name of the PC hosting the web app.

There are 2 known reasons why the web app may not launch properly:
1. One of the above mentioned paths does not exist.  The default paths are created by a standard install of hobl, so if any customizations were done, make sure they align.
2. Port 80 is in use by something else.  There are two possible remedies to this:
    1. If you don't need to make the website available for remote access, you can change the port.  You can do this by adding the HOBLWEB_URL environment variable that includes a different port.  For example, to use port 5000, set an the variable to "http://localhost:5000"
    2. If you want to keep it at port 80, such as for the purpose of remote access through a firewall, then you can stop the processes currently using port 80 (they usually are not important), but issuing the command, "net stop http" from an admin terminal.  Sometimes a service that has been stopped will immediately restart and consume the port again.  To find this, run "net stop http" again and see which service is running again.  Then go to Windows Services and set that service to "Disabled".

## Device Profiles
A Device Profile defines key test parameters for the Device Under Test, and can be organized into folders for large labs.  The profile information is kept in a local database.  To perform an action on a profile, either right-click it or select it and use the buttons at the top.  Note that some actions, such as Launch and Delete can be performed on multiple profiles, so be careful to note what all profiles are selected when you perform these actions.

#### Actions
* **Import** - Imports profile information in *.ini or Excel *.xlsx format, into the local database.  For *.ini format see the default.ini that comes with HOBL.  For the Excel format, do an export of existing profiles.
* **Export** - Exports selected profiles in Excel *.xlsx format.  Each row is a profile, and the parameters are in the columns.
* **Edit** - Opens a form to edit the parameter values of the profile.
* **Copy** - Copies a profile by opening the Edit form and prompting you to give a new name.  You can modify any other parameter values at this time.
* **Launch Job** - Launches jobs on the selected profiles, by taking you the "Submit a New Job" page.
* **Delete** - Deletes the selected profiles.

#### Parameters
Parameters are either "global" (applying to every scenario), or are specific to a particular scenario or tool.  The section header on the profile Edit page identifies what the parameter applies to.

* **global:result_dir** - This is where the results of a *study* will be stored on disk.  The default root storage location is c:\hobl_results, and the first part of the result_dir parameter needs to match.  If a different location is desired it needs to be changed in the appsettings.json file in the hoblweb folder, and the webserver needs to be restarted.  The last element of the path is called the "study" and indicates the variable being studied for this set of tests, such as a particular OS build, browser version, etc.  The "study report" will be written here and roll up the results of all the tests beneath this path.  **It's important to not attempt to nest a study underneath another study.**
* **global:hobl_path** - This parameter can be used to point to a different location for the base hobl code, in case different versions of the code want to be maintained.  The default is "c:\hobl".

## Jobs
When you launch a job on a profile, it will take you to the "Submit a New Job" page where you can select to load either a test plan or an individual scenario.  It is recommended to always run from an appropriate test plan if possible, because the test plans add command-line parameters to organize results into run type sub-folders, and add key tools and settings.  Even if you just want to run a single scenario, it's better to open the whole test plan and just select the scenario(s) you want to run from it.  If you need to run a scenario that is not part of a plan, that's when you would select an individual scenario(s) from the "Add Scenario" drop down to build up a custom plan.  Scenarios can also be added to loaded test plans by selecting from "Add Scenario".

The "Check Preps" checkbox will insert a "prep" scenario when launched that will run any needed prep scenarios for the test scenarios in the plan.  If preps have already been ran, they won't be reran.

The "Auto Resubmit" selection, will automatically run the test plan again once the previous completes, for the specified number of times.

When you load a plan or add scenarios, the table at the bottom shows the scenarios.  Here you can select or deselect the scenarios you want to run, modify/add any command-line parameter overrides, and choose how many iterations of each scenario to run.  You can also drag and drop to re-order the scenarios by grabbing the left side of the row.  Scenarios can be removed by clicking the "Delete Selected" button at the top.  Once your plan is the way you want it, click the "Submit" button to submit it for execution.  This will take you to the "Scenarios" page, and if no other jobs are currently running on the device it will execute immediately, otherwise it will be in the "Pending" state until previous jobs are finished.

The Scenarios page shows a table of each scenario in the plan in the order that they will be executed, and the current status: PENDING, ACTIVE, PASS, FAIL, TERMINATED.  The "Run Dir" column links to the Results page for that particular run.  Clicking the "Stop" button at the top will terminate the currently running scenario (calling the kill routine of the scenario), and prevent execution of the rest of the scenarios in the plan.  The "Resubmit" button will take you to the "Submit a New Job" page with the same scenarios and settings preloaded, so that you can just hit the "Submit" button to run again, or take the opportunity to make any tweaks first.

The Jobs page lists the history of test plans that have been submitted, summarizes how many of the scenarios in the plan have passed and failed, and links to the Results page for the overall study.  You can click the ID on the left, or double-click the row, to go to the corresponding Scenarios page.  Clicking the plan name in the row will take you back to relaunch the job.

## Recent Runs
This page lists the most recent runs that have been submitted.  They can be filtered and sorted to see such things as the failed runs of a particular scenario or study.

## Summary
This page allows you to see how many passing and failing runs there have been for a particular plan for a particular study.  This useful, for example, for seeing if all the preps have passed, or if the desired number of runs of each scenario for a particular study have completed.

## Results
The Results page works like a file explorer.  The "bread crumbs" at the top allow you to navigate back up levels of the hierarchy.  Click into a folder will take you down the hierarchy.  Run folders that are colored green are tests that have PASSed, while red ones are tests that have FAILed.  Many of the files produced by runs are directly viewable in the web interface for speed and convenience.  These include the html study report, csv files, html sleepstudy and battery reports, screen capture images, and video captures.  Files in the .trace format are a special form of CSV, that viewer show as an interactive plot, that can be combined and overlaid with other .trace files.  For example, overlaying the processes.trace onto the power.trace will show which process might have kicked up during a power spike.  Other files that are not viewable, such as .etl and .tdms files will instead be downloaded to your local computer for viewing when you click on them.

In each run folder, the *_metrics.csv file rolls up all the key metrics from the run, including configuration information gathered before and after the run.  When the "study_report" scenario is run, a .xlsx and corresponding .html report file is produced at the study level.

## Documentation
The Documentation page presents all the docs found in the hobl docs\support folder.  So these documents get updated with hobl updates and are independent of the HOBLweb UI version.
