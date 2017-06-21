HOME=/home/gustaf
BIN=$(HOME)/prj/BTCPriceTicker
#BUILD=$(HOME)/prj/RegNr/build
CGI=$(HOME)/cgi-bin

deploy: ticker.cgi
	cp $(BIN)/ticker.cgi $(CGI)/ticker.cgi

.PHONY: test
test: 
	perl -Tc ticker.cgi > test 
	perl -T ticker.cgi o=irc >> test
	perl -T ticker.cgi o=console | perl -pe 's/\e\[?.*?[\@-~]//g' >> test
	perl -T ticker.cgi o=mcap | perl -pe 's/\e\[?.*?[\@-~]//g' >> test
	perl -T ticker.cgi o=html|lynx -stdin -dump >> test
	perl -T ticker.cgi o=json > json

deploy-test:
	curl -s http://gerikson.com/cgi-bin/ticker.cgi | lynx -stdin -dump >> test
