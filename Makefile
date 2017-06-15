HOME=/home/gustaf
BIN=$(HOME)/prj/BTCPriceTicker
#BUILD=$(HOME)/prj/RegNr/build
CGI=$(HOME)/cgi-bin

deploy: ticker.cgi
	cp $(BIN)/ticker.cgi $(CGI)/ticker.cgi
