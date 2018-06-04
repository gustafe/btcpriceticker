HOME=/home/gustaf
BIN=$(HOME)/bin
BUILD=$(HOME)/BTCPriceTicker/About-page/build
MARKDOWN=$(BIN)/Markdown_1.0.1/Markdown.pl
WWW=$(HOME)/public_html/btcticker

deploy: about.html
	cp $(BUILD)/about.html $(WWW)/about.html

#test-deploy: faq.html
#	cp $(BUILD)/faq.html $(WWW)/t/faq.html

#test-newfaq: newfaq
#	cp $(BUILD)/newfaq.html $(WWW)/t/newfaq.html


about.html: *.txt about.head about.foot generate_changelog.pl
	cat about.head > $(BUILD)/about.html
	perl generate_changelog.pl > 11.changelog.txt
	cat *.txt | $(MARKDOWN) >> $(BUILD)/about.html
	cat about.foot >> $(BUILD)/about.html

about.txt: *.txt
	cat *.txt >> $(BUILD)/about.txt

# newfaq: [0-9][0-9][0-9]_*.txt faq.head faq.foot
# 	cat faq.head > $(BUILD)/newfaq.html
# 	perl ./new-generate-faqpage.pl | $(MARKDOWN) >> $(BUILD)/newfaq.html
# 	cat faq.foot >> $(BUILD)/newfaq.html

clean-test: test-deploy
	rm $(WWW)/t/*.html
