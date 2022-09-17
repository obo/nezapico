SHELL=/bin/bash

.PHONY: show-correlations
show-correlations: temp-correlations.tab
	cat $< \
	| skip 1 \
	| mynl \
	| labelledxychart --data=1,2,0,'mid',linespoints --data=1,3,5,'top',linespoints --data=1,4,0,'sensor',linespoints \
	| gpsandbox
