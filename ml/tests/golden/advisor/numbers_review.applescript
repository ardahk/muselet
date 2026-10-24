tell application id "com.apple.Numbers"
	tell front document
		set nm to "Muselet Review"
		if exists sheet nm then
			if exists table "Muselet Allocation" of sheet nm then
				delete sheet nm
			else
				set i to 2
				repeat while exists sheet (nm & " " & i)
					set i to i + 1
				end repeat
				set nm to nm & " " & i
			end if
		end if
		set s to make new sheet with properties {name:nm}
		tell s
			set t1 to table 1
			set name of t1 to "Muselet Allocation"
			set column count of t1 to 6
			set row count of t1 to 6
			set value of cell 1 of row 1 of t1 to "Asset class"
			set value of cell 2 of row 1 of t1 to "Value"
			set value of cell 3 of row 1 of t1 to "Current %"
			set value of cell 4 of row 1 of t1 to "Target %"
			set value of cell 5 of row 1 of t1 to "Drift (pp)"
			set value of cell 6 of row 1 of t1 to "Post-trade %"
			set value of cell 1 of row 2 of t1 to "US equity"
			set value of cell 2 of row 2 of t1 to 714056.00
			set value of cell 3 of row 2 of t1 to 47.50
			set value of cell 4 of row 2 of t1 to 40.00
			set value of cell 5 of row 2 of t1 to 7.50
			set value of cell 6 of row 2 of t1 to 40.00
			set value of cell 1 of row 3 of t1 to "Intl equity"
			set value of cell 2 of row 3 of t1 to 306160.00
			set value of cell 3 of row 3 of t1 to 20.37
			set value of cell 4 of row 3 of t1 to 20.00
			set value of cell 5 of row 3 of t1 to 0.37
			set value of cell 6 of row 3 of t1 to 20.00
			set value of cell 1 of row 4 of t1 to "Bonds"
			set value of cell 2 of row 4 of t1 to 407960.00
			set value of cell 3 of row 4 of t1 to 27.14
			set value of cell 4 of row 4 of t1 to 35.00
			set value of cell 5 of row 4 of t1 to -7.86
			set value of cell 6 of row 4 of t1 to 35.00
			set value of cell 1 of row 5 of t1 to "Cash"
			set value of cell 2 of row 5 of t1 to 75000.00
			set value of cell 3 of row 5 of t1 to 4.99
			set value of cell 4 of row 5 of t1 to 5.00
			set value of cell 5 of row 5 of t1 to -0.01
			set value of cell 6 of row 5 of t1 to 5.00
			set value of cell 1 of row 6 of t1 to "Equity total"
			set value of cell 2 of row 6 of t1 to 1020216.00
			set value of cell 3 of row 6 of t1 to 67.87
			set value of cell 4 of row 6 of t1 to 60.00
			set value of cell 5 of row 6 of t1 to 7.87
			set value of cell 6 of row 6 of t1 to 60.00
			set format of range "B2:B6" of t1 to currency
			set t2 to make new table with properties {name:"Muselet Trades", column count:6, row count:4}
			set {x0, y0} to position of t1
			set position of t2 to {x0, y0 + (height of t1) + 40}
			set value of cell 1 of row 1 of t2 to "Account"
			set value of cell 2 of row 1 of t2 to "Side"
			set value of cell 3 of row 1 of t2 to "Ticker"
			set value of cell 4 of row 1 of t2 to "Asset class"
			set value of cell 5 of row 1 of t2 to "Amount"
			set value of cell 6 of row 1 of t2 to "Note"
			set value of cell 1 of row 2 of t2 to "Mark Traditional IRA"
			set value of cell 2 of row 2 of t2 to "sell"
			set value of cell 3 of row 2 of t2 to "VTI"
			set value of cell 4 of row 2 of t2 to "US equity"
			set value of cell 5 of row 2 of t2 to 112785.60
			set value of cell 6 of row 2 of t2 to ""
			set value of cell 1 of row 3 of t2 to "Mark Traditional IRA"
			set value of cell 2 of row 3 of t2 to "sell"
			set value of cell 3 of row 3 of t2 to "VXUS"
			set value of cell 4 of row 3 of t2 to "Intl equity"
			set value of cell 5 of row 3 of t2 to 5524.80
			set value of cell 6 of row 3 of t2 to ""
			set value of cell 1 of row 4 of t2 to "Mark Traditional IRA"
			set value of cell 2 of row 4 of t2 to "buy"
			set value of cell 3 of row 4 of t2 to "AGG"
			set value of cell 4 of row 4 of t2 to "Bonds"
			set value of cell 5 of row 4 of t2 to 118151.60
			set value of cell 6 of row 4 of t2 to "instead of BND (wash sale)"
			set format of range "E2:E4" of t2 to currency
		end tell
		set active sheet to s
	end tell
end tell
