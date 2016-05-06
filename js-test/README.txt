Configuration
-------------

1. Install JS Test Driver plugin from http://js-test-driver.googlecode.com/svn/update/ 

2. Restart Eclipse

3. In Eclipse preferences, go to JS Test Driver
	* Path to Safari: /Applications/Safari.app/Contents/MacOS/Safari
	* Path to Chrome: /Applications/Google Chrome.app/Contents/MacOS/Google Chrome
	* Optionally configure more browser if you want to test on one of them
		* Path to Firefox: /Applications/Firefox.app/Contents/MacOS/firefox

4. Right click a unittest file (eg. js_mfr.js)
	* Run as > Run Configurations ...
	* Select Js Test Driver Test
	* Press the 'New' button (top left icon) to create a new run configuration
	* Project: <select appengine project>
	* Conf file: <select js-test/jsTestDriver.conf>

Running unit tests
------------------

1. Go to Window > Show view > Other ... > JS Test Driver View
	* The top part of the view is the Server info panel.
	* Start the server by pressing the green play button
	* Click the icon(s) of the browser(s) which you want to run the tests on

2. Select the .js unit test file(s) and right click: Run as > JS Test Driver Test