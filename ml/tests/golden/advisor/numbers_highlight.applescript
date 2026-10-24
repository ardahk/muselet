tell application id "com.apple.Numbers"
	tell table 1 of sheet "Holdings" of front document
		set background color of range "A13:J13" to {50886, 61423, 52942} -- BND 2021-08-02 ok
		set background color of range "A5:J5" to {50886, 61423, 52942} -- VNQ 2022-01-03 ok
		set background color of range "A11:J11" to {65535, 58853, 39321} -- VXUS 2026-02-09 wash_sale_blocked
	end tell
end tell
