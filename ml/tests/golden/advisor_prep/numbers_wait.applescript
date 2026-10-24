tell application id "com.apple.Numbers"
	set theDoc to missing value
	repeat 40 times
		repeat with d in documents
			try
				if POSIX path of ((file of d) as alias) is "<CLIENTS>/Henderson/portfolio.xlsx" then set theDoc to contents of d
			end try
		end repeat
		if theDoc is not missing value then exit repeat
		delay 0.1
	end repeat
	if theDoc is missing value then error "Numbers has no open document for <CLIENTS>/Henderson/portfolio.xlsx"
	return POSIX path of ((file of theDoc) as alias)
end tell
