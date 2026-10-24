tell application id "com.apple.Numbers"
	repeat 100 times
		if (count of (every document whose name starts with "portfolio")) > 0 then exit repeat
		delay 0.1
	end repeat
	return name of first document whose name starts with "portfolio"
end tell
