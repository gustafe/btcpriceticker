HOME=/home/gustaf
BIN=$(HOME)/prj/BTCPriceTicker
#BUILD=$(HOME)/prj/RegNr/build
CGI=$(HOME)/cgi-bin

deploy: ticker.cgi
	cp $(BIN)/ticker.cgi $(CGI)/ticker.cgi

test: ticker.cgi
	perl -Tc ticker.cgi > test 
	perl -T ticker.cgi o=irc >> test
	perl -T ticker.cgi o=console >> test
	perl -T ticker.cgi o=html|lynx -stdin -dump >> test
	perl -T ticker.cgi o=json > json
