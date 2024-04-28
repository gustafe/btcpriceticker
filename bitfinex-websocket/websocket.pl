#! /usr/bin/env perl
use Modern::Perl '2015';
###

use IO::Async::Loop;
use Net::Async::WebSocket::Client;
my $testing=0; 
my $client = Net::Async::WebSocket::Client->new(
   on_text_frame => sub {
      my ( $self, $frame ) = @_;
      print '--> '.$frame;
   },
);
my ( $server, $msg );
if ($testing) {
    ($server, $msg ) = ('wss://echo.websocket.org',"echo test\n");
    
} else {
    ($server, $msg ) = ("wss://api-pub.bitfinex.com/ws/2", "{ \"event\": \"subscribe\",  \"channel\": \"ticker\",  \"symbol\": \"tBTCUSD\" }\n");
}

my $loop = IO::Async::Loop->new;
$loop->add( $client );
 
$client->connect(
   url => $server,
)->then( sub {
   $client->send_text_frame( $msg );
})->get;
 
$loop->run;
