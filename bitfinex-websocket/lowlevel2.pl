#!/usr/bin/env perl
use v5.014;
use warnings;
# Perl WebSocket test client
#  Greg Kennedy 2019
# IO::Socket::SSL lets us open encrypted (wss) connections
use IO::Socket::SSL;
# IO::Select to "peek" IO::Sockets for activity
use IO::Select;
# Protocol handler for WebSocket HTTP protocol
use Protocol::WebSocket::Client;
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
say "Attempting to open SSL socket to $proto://$host:$port...";
# create a connecting socket
#  SSL_startHandshake is dependent on the protocol: this lets us use one socket
#  to work with either SSL or non-SSL sockets.
my $tcp_socket = IO::Socket::SSL->new(
PeerAddr => $host,
PeerPort => "$proto($port)",
Proto => 'tcp',
SSL_startHandshake => ($proto eq 'wss' ? 1 : 0),
Blocking => 1
) or die "Failed to connect to socket: $@";
# create a websocket protocol handler
#  this doesn't actually "do" anything with the socket:
#  it just encodes / decode WebSocket messages.  We have to send them ourselves.
say "Trying to create Protocol::WebSocket::Client handler for $url...";
my $client = Protocol::WebSocket::Client->new(url => $url);
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
}
);
# Now that we've set all that up, call connect on $client.
#  This causes the Protocol object to create a handshake and write it
#  (using the on_write method we specified - which includes sysread $tcp_socket)
say "Calling connect on client...";
$client->connect;
# read until handshake is complete.
while (! $client->{hs}->is_done)
{
my $recv_data;
my $bytes_read = sysread $tcp_socket, $recv_data, 16384;
if (!defined $bytes_read) { die "sysread on tcp_socket failed: $!" }
elsif ($bytes_read == 0) { die "Connection terminated." }
$client->read($recv_data);
}
# Create a Socket Set for Select.
#  We can then test this in a loop to see if we should call read.
my $set = IO::Select->new($tcp_socket, \*STDIN);
while (1) {
# call select and see who's got data
my ($ready) = IO::Select->select($set);
foreach my $ready_socket (@$ready) {
# read data from ready socket
my $recv_data;
my $bytes_read = sysread $ready_socket, $recv_data, 16384;
# handler by socket type
if ($ready_socket == \*STDIN) {
# Input from user (keyboard, cat, etc)
if (!defined $bytes_read) { die "Error reading from STDIN: $!" }
elsif ($bytes_read == 0) {
# STDIN closed (ctrl+D or EOF)
say "Connection terminated by user, sending disconnect to remote.";
$client->disconnect;
$tcp_socket->close;
exit;
} else {
chomp $recv_data;
$client->write($recv_data);
}
} else {
# Input arrived from remote WebSocket!
if (!defined $bytes_read) { die "Error reading from tcp_socket: $!" }
elsif ($bytes_read == 0) {
# Remote socket closed
say "Connection terminated by remote.";
exit;
} else {
# unpack response - this triggers any handler if a complete packet is read.
$client->read($recv_data);
}
}
}
}
