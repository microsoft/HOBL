# Developing UI-based Scenarios

This guide covers developing and maintain scenarios that interact with GUI-based applications.  The primary tool for this is Scenario Maker.  See the [Scenario Maker documentation](HOBL_ScenarioMaker.md) for general use of Scenario Maker.

For best results, follow these guidelines:

- For the capture device, 150% Windows Scaling factor is recommended, with fairly high screen resolution (doesn't have to be 4K, though).
- Minimize capture size to minimize power impact, but be sure to include enough to cover different screen layouts.
- Minimize capture frequency to minimize power impact.  Re-use where possible.
- For button click templates, capture text without the surrounding box because the box spacing relative to the text can change.
- Don't capture elements that can change on different systems, like volume slider.
- Avoid code blocks.  They may be necessary, but consider it a red flag.  Maybe what you're trying to accomplish is something we should bake into the infrastructure, so talk to us about it.
- If you're not sure the best way to do something, ask.
- Do not use Check Until in a measured scenario.  This should be used for non-measured preps only.