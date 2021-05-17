#!/usr/bin/perl -T
# -*- CPerl -*-
use Modern::Perl '2015';


###

use CGI qw(:standard start_ul *table -utf8);
use CGI::Carp qw(fatalsToBrowser);
use Number::Format;
use Template;
use FindBin qw/$Bin/;
use utf8;

binmode( STDOUT, ":utf8" );

sub nformat {
    my ($in) = @_;

    my $nf = new Number::Format;
    return $nf->format_number( $in, 2, 2 );
}


sub commify {
    my $text = reverse $_[0];
    $text =~ s/(\d\d\d)(?=\d)(?!\d*\.)/$1,/g;
    return scalar reverse $text;
}
sub large_num {    # return numbers in K, M, B based on size
    my ($x) = @_;
    my $negative = 1 if $x < 0;
    $x = -$x if $negative;
    return $negative ? -$x : $x if $x < 1_000;
    return sprintf( "%.02fk", $negative ? -$x / 1_000 : $x / 1_000 )
      if ( $x >= 1_000 and $x < 1_000_000 );
    return sprintf( "%.02fM", $negative ? -$x / 1_000_000 : $x / 1_000_000 )
      if ( $x >= 1_000_000 and $x < 1_000_000_000 );
    return
      sprintf( "%.02fB", $negative ? -$x / 1_000_000_000 : $x / 1_000_000_000 )
      if ( $x >= 1_000_000_000 );
}

my $query = new CGI;
my $tt    = Template->new(
    {   INCLUDE_PATH => "$Bin/templates",
        ENCODING     => 'UTF-8'
    }
);
my $test    = $query->param('t')       || '';
my $console = $query->param('console') || '';
my $text    = $query->param('text')    || '';

my $last = 46_162;
my $last_update = 'Sun 16 May 2021 09:17:58';

my $farewell = <<'FAREWELL';
This site is no more (or rather, it is no longer being actively updated with BTC price information).

Recently, Bitcoinaverage has raised the minimum price for API access
to USD&nbsp;12/mo. This is too much for me for a hobby project.

Thanks to my loyal users. I know they're few, but they're out there and I appreciate it.
FAREWELL

my $draper = {
    coins             => 29656.51306529,
    price_at_purchase => 600,
    purchase_value    => 600 * 29656.51306529,
    current_value     => $last * 29656.51306529,
    win_loss          => ( $last - 600 ) * 29656.51306529
};
my @draper = map { $draper->{$_} } qw/coins price_at_purchase/;
my @past_events = (
        {
            header  => "Price of a 2017 Lamborghini LP 750-4 SV Roadster",
            content => [
                "The price of this car is USD&nbsp;535,500. The price in BTC is "
                  . sprintf( "%.05f BTC.", 535500 / $last )
		       ],
	 anchor=>'lambo',
        },

        {
            header  => "Tim Draper's coins from Silk Road",
            content => [
                sprintf(
"On 27 Jun 2014, investor Tim Draper paid approximately USD&nbsp;%.02f/coin for %s BTC seized from Silk Road. ",
                    $draper[1], $draper[0]
                ),
                sprintf( "Purchase price: USD&nbsp;%s",
                    large_num( $draper[0] * $draper[1] ) ),
                sprintf( "Price now: USD&nbsp;%s",
                    large_num( $draper[0] * $last ) ),
                sprintf( "Draper's win/loss: USD&nbsp;%s",
                    large_num( $draper[0] * ( $last - $draper[1] ) ) ),
		       ],
	 anchor=>'draper',
        },
		       
        {
            header  => "The Bitcoin pizza",
            content => [
"On 22nd May 2010, Bitcoin enthusiast Laszlo Hanyec bought a pizza for 10,000 bitcoins. More specifically, he sent the coins to someone else who purchased the pizza for him.",
                sprintf( "The Bitcoin pizza is currently worth USD&nbsp;%s.",
                    nformat( 10_000 * $last ) ),
"See the <a href='https://twitter.com/bitcoin_pizza'>\@bitcoin_pizza</a> Twitter account for up-to-date values!",
		       ],
	 anchor=>'pizza',
        },
		       
        {
            header  => "The white Mini Cooper",
            content => [
                sprintf(
"On 7 Jun 2014, Andreas M. Antonopoulos offered a white Mini Cooper for sale for 14BTC. At the time, the VWAP was USD&nbsp;652.76, so the sales price (assuming it went through) was USD&nbsp;%s.",
                    nformat( 14 * 652.76 ) ),
                sprintf( "Today, the same car is worth USD&nbsp;%s.",
                    nformat( 14 * $last ) ),
"(Source: <a href='https://twitter.com/aantonop/status/475048024453152768'>\@aantonop tweet</a>.)"
		       ],
	 anchor=>'mini',
        },
        {
            header  => "2016 Bitfinex hack",
            content => [
"On 2 Aug 2016, the exchange Bitfinex announced they had suffered a security breach and that 119,756 BTC were stolen.",
                sprintf( "Current value of the stolen coins is USD&nbsp;%s.",
                    nformat( 119_756 * $last ) )
		       ],
	 anchor=>'bitfinex',
        },
        {
            header  => "Price of a Leica Noctilux-M 75mm f/1.25 ASPH lens",
            content => [
"The price of this lens was USD&nbsp;12,795 at announcement. The price of this lens in BTC is "
                  . sprintf( "%.05f BTC.", 12795 / $last )
		       ],
	 anchor=>'leica',
        },
		       {header=>"Value of the drug-dealer's fishing rod cap",
			content =>["The convicted drug dealer Clifton Collins <a href='https://www.theguardian.com/world/2020/feb/21/irish-drug-dealer-clifton-collins-l46m-bitcoin-codes-hid-fishing-rod-case'>hid the codes to 6,000 BTC in a fishing rod cap that was thrown away when he was in jail</a>. The coins are now worth USD&nbsp;".sprintf("%s.",nformat(6_000*$last))],
			anchor=>'fishing-rod',
		       },

		      );


my %data = ( meta     => { page_title => "World's slowest BTC tracker RIP 💀" },
   content => {last_price => nformat($last),
	       last_update => $last_update,
	       past_events => \@past_events,
	       farewell => $farewell,
	      },
);
my $out = '';

$out = header( { -type => 'text/html', -charset => 'utf-8' } );
$tt->process( "tracker_rip.tt", \%data, \$out ) or die $tt->error;

print $out;
