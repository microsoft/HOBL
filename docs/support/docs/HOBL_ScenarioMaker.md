# Scenario Maker
* Scenario Maker is an application that facilitates the creation of new test scenarios (or editing existing ones).
* Run Scenario Maker by executing hobl\ScenarioMaker\ScenarioMaker.cmd.
* It starts with a remote connection to a DUT (specify IP address in Settings), then allows you to compose a sequence of actions for the scenario using the menu.
* Record mode records you interacting with the DUT as a user would, and generates the appropriate action sequence for the test quickly and easily.  Caution, though, as these won't be optimized for power consumption.  To minimize power consumption, only take new screen captures when what you want to capture wasn't in a previous capture, and only capture as much of the screen as necessary.  Smaller screen region captures are faster and use less power.

