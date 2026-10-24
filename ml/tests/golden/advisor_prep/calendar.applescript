tell application id "com.apple.iCal"
	activate
	set d0 to (current date) - (time of (current date))
	set d1 to d0 + 30 * days
	set best to missing value
	repeat with c in calendars
		repeat with e in (every event of c whose summary contains "Henderson" and start date is greater than or equal to d0 and start date is less than d1)
			if best is missing value then
				set best to contents of e
			else if start date of e < start date of best then
				set best to contents of e
			end if
		end repeat
	end repeat
	if best is missing value then return ""
	set s to start date of best
	switch view to day view
	view calendar at s
	return (summary of best) & linefeed & (s as «class isot» as string) & linefeed & ((end date of best) as «class isot» as string)
end tell
