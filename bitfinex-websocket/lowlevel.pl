#!/usr/bin/env perl
use v5.014;
use warnings;
# Simple WebSocket test client using blocking I/O
#  Greg Kennedy 2019
# Core IO::Socket::INET for creating sockets to the Internet
use IO::Socket::INET;
# Protocol handler for WebSocket HTTP protocol
use Protocol::WebSocket::Client;
# Uncomment this line if your IO::Socket::INET is below v1.18 -
#  it enables auto-flush on socket operations.
#$|= 1;
#####################
die "Usage: $0 URL" unless scalar @ARGV == 1;
my $url = $ARGV[0];
# Protocol::WebSocket takes a full URL, but IO::Socket::* uses only a host
#  and port.  This regex section retrieves host/port from URL.
my ($proto, $host, $port, $path);
if ($url =~ m/^(?:(?<proto>ws|wss):\/\/)?(?<host>[^\/:]+)(?::(?<port>\d+))?(?<path>\/.*)?$/)
{
$host = $+{host};
$path = $+{path};
if (defined $+{proto} && defined $+{port}) {
$proto = $+{proto};
$port = $+{port};
} elsif (defined $+{port}) {
$port = $+{port};
if ($port == 443) { $proto = 'wss' } else { $proto = 'ws' }
} elsif (defined $+{proto}) {
$proto = $+{proto};
if ($proto eq 'wss') { $port = 443 } else { $port = 80 }
} else {
$proto = 'ws';
$port = 80;
}
} else {
die "Failed to parse Host/Port from URL.";
}
say "Attempting to open blocking INET socket to $proto://$host:$port...";
# create a basic TCP socket connected to the remote server.
my $tcp_socket = IO::Socket::INET->new(
PeerAddr => $host,
PeerPort => "$proto($port)",
Proto => 'tcp',
Blocking => 1
) or die "Failed to connect to socket: $@";
# create a websocket protocol handler
#  this doesn't actually "do" anything with the socket:
#  it just encodes / decode WebSocket messages.  We have to send them ourselves.
say "Trying to create Protocol::WebSocket::Client handler for $url...";
my $client = Protocol::WebSocket::Client->new(url => $url);
# This is a helper function to take input from stdin, and
#  * if "exit" is entered, disconnect and quit
#  * otherwise, send the value to the remote server.
sub get_console_input
{
say "Type 'exit' to quit, anything else to message the server.";
# get something from the user
my $input;
do { $input = <STDIN>;  chomp $input } while ($input eq '');
if ($input eq 'exit') {
$client->disconnect;
exit;
} else {
$client->write($input);
}
}
# Set up the various methods for the WS Protocol handler
#  On Write: take the buffer (WebSocket packet) and send it on the socket.
$client->on(
write => sub {
my $client = shift;
my ($buf) = @_;
syswrite $tcp_socket, $buf;
}
);
# On Connect: this is what happens after the handshake succeeds, and we
#  are "connected" to the service.
$client->on(
connect => sub {
my $client = shift;
# You may wish to set a global variable here (our $isConnected), or
#  just put your logic as I did here.  Or nothing at all :)
say "Successfully connected to service!";
get_console_input();
}
);
# On Error, print to console.  This can happen if the handshake
#  fails for whatever reason.
$client->on(
error => sub {
my $client = shift;
my ($buf) = @_;
say "ERROR ON WEBSOCKET: $buf";
$tcp_socket->close;
exit;
}
);
# On Read: This method is called whenever a complete WebSocket "frame"
#  is successfully parsed.
# We will simply print the decoded packet to screen.  Depending on the service,
#  you may e.g. call decode_json($buf) or whatever.
$client->on(
read => sub {
my $client = shift;
my ($buf) = @_;
say "Received from socket: '$buf'";
# it's our "turn" to send a message.
get_console_input();
}
);
# Now that we've set all that up, call connect on $client.
#  This causes the Protocol object to create a handshake and write it
#  (using the on_write method we specified - which includes sysread $tcp_socket)
say "Calling connect on client...";
$client->connect;
# Now, we go into a loop, calling sysread and passing results to client->read.
#  The client Protocol object knows what to do with the data, and will
#  call our hooks (on_connect, on_read, on_read, on_read...) accordingly.
while ($tcp_socket->connected) {
# await response
my $recv_data;
my $bytes_read = sysread $tcp_socket, $recv_data, 16384;
if (!defined $bytes_read) { die "sysread on tcp_socket failed: $!" }
elsif ($bytes_read == 0) { die "Connection terminated." }
# unpack response - this triggers any handler if a complete packet is read.
$client->read($recv_data);
}
