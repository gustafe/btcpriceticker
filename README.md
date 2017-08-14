# About my little Bitcoin price tracker

Updated [about page](http://gerikson.com/btcticker/about.html).

This web script reads current and historical prices from [Bitcoinaverage](https://bitcoinaverage.com/markets#USD) and presents the prices from some selected points in time.

There's a "semi-logarithmic" timescale of 3 day, 1 week, 1 month (30 days), 6 months, and 1 year. In addition, price from 1 Jan of the current year, this year's high, and this year's low are included. 

I've also included the current (Sep 2014) record high price from Nov 2013.

In the data files from Bitcoinaverage, historical days have average, high, and low volume-weighted prices. The prices in the tables are average for each day, except of the highs and lows mentioned above.




## <a id="current"></a>Current price compared to historical prices

### Percentage calculations

The percentage in the table is 

    percentage = ( current_price - historical_price ) / historical_price * 100

This means that the current price is calculated using the formula

    current_price = historical_price * (1 + percentage/100)

### Market cap

The number of coins at a certain date is calculated using extrapolated values from [this page](https://en.bitcoin.it/wiki/Controlled_supply) and multiplied with the price.

Note that this is a naive definition of "market cap" and not really applicable to Bitcoin, as it's not a share in a company. However it's widely used as a sort of benchmark within the community.
## <a id='extrapolated'></a>Historical prices compared to extrapolated trends

It's often postulated that Bitcoin's underlying price development is
exponential (or rather, that it's in the "exponential" phase of a
S-shaped saturation curve). To compare this, I calculated a best-fit
line approximation against the natural log of the the average
historical price, and this calculated price is presented compared to
the actual prices.

I've also compared to a linear approximation, using the same
methodology but of course using the straight numbers.

I've excluded all data newer than 3 days. The coefficients are updated
daily. The values are shown in the headers.

I've used Julian dates to deal with the days, mostly because SQLite has built-in support for the datatype.
## <a id="future"></a> Future extrapolations

### Red Anniversary 

A received truth is that "no-one has ever lost money holding Bitcoin for one calendar year". We're a few months from testing that hypothesis. On the days leading up to 29 Nov 2014, the price rocketed from $130 to $1,100. 

As there's often no direct average price that's the same as the
current price, I've extrapolated the current price based on the slope
of the price increase. I've then added 365 days to that extrapolated
time and called that "red anniversary". If there's no new record high
before 29 Nov 2014, a buyer of Bitcoin will be "in the red" after a
year.

###  Future prices based on linear trend from Nov 2013 peak

This line is based on averages since Nov 2013. 
## FAQ

Q: why Perl? Why CGI? Are you some kind of Luddite?

A: Yes, it's what I'm most familiar with, and what's available on the server I'm using. I'm more interested in dealing with the actual data analysis, and I'm using tools I know about to deal with it.

Q: I love this page! Do you take Bitcoin donations?

A: I don't have a Bitcoin wallet, but I have a tip jar on Reddit. You can use that if you want. But I'd prefer if you'd donate to a charity instead. I don't need the money.
## <a id="Contact"></a> Contact

Questions? Comments? I'm ``gerikson`` on Twitter and Reddit.
