HOME=/home/gustaf
BIN=$(HOME)/BTCPriceTicker
#BUILD=$(HOME)/prj/RegNr/build
CGI=$(HOME)/cgi-bin
TEMPLATES=$(BIN)/templates

deploy: ticker.cgi $(TEMPLATES)/tracker_rip.tt
	cp $(BIN)/ticker.cgi $(CGI)/ticker.cgi
	cp $(TEMPLATES)/tracker_rip.tt $(CGI)/templates/tracker_rip.tt

.PHONY: test
test: 
	perl -Tc ticker.cgi          > test 
	perl -T ticker.cgi o=irc     >> test
	perl -T ticker.cgi o=console | perl -pe 's/\e\[?.*?[\@-~]//g' >> test
	perl -T ticker.cgi o=mcap    | perl -pe 's/\e\[?.*?[\@-~]//g' >> test
	perl -T ticker.cgi o=html    | lynx -stdin -dump >> test
	perl -T ticker.cgi o=json    > json

deploy-test:
	curl -s http://gerikson.com/cgi-bin/ticker.cgi | lynx -stdin -dump >> test
