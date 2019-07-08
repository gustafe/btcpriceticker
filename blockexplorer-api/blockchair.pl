#!/usr/bin/perl
use strict;
use warnings;
use DBI;
use Text::CSV;
use LWP::UserAgent;

#use LWP::Simple;
use JSON;
use POSIX::strptime;
use POSIX qw(strftime);
use DateTime;
use DateTime::Format::Strptime;
use Data::Dumper;
use Getopt::Long;

#### Connections
my $update_future = 0;
my $driver        = 'SQLite';
my $database      = '/home/www/gerikson.com/cgi-bin/data/historical-prices.db';
my $dsn           = "DBI:$driver:dbname=$database";
my ( $user, $pass ) = ( '', '' );
my $dbh;
my $sth;
my $base_url = 'https://api.blockchair.com';
my %Sql;
my $strp = DateTime::Format::Strptime->new(
					   pattern=>'%Y-%m-%d %H:%M:%S',
					   on_error => 'croak' );

#### Helper subs

sub coins_per_block {
    my ($blocks) = @_;
    return undef unless $blocks > 0;
    my $reward = 50;
    my $period = 210_000;
    my $diff   = 0;
    my $coins  = 0;

    while ( $diff >= 0 ) {
        $diff = $blocks - $period;
        $coins += ( $diff < 0 ? $blocks * $reward : $period * $reward );
        $blocks = $diff;
        $reward = $reward / 2;
    }
    return $coins;
}

sub get_ua {
    my $ua = LWP::UserAgent->new;
    $ua->agent(
'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36'
    );

    return $ua;
}
my $ua = get_ua();

sub web_data {
    my ( $api_string, $param ) = @_;

    print "querying $base_url/$api_string...\n";

    my $res = $ua->get("$base_url/$api_string");
    my $json;
    if ( !$res->is_success ) {
        warn "==> request failed!\n";
        warn $res->status_line . "\n";
        return undef;
    }
    else {
        $json = $res->decoded_content;
    }

    my $info = decode_json($json);

    if ( $api_string =~ /status/ ) {
        return $info->{info}->{$param};
    }
    else {
        return $info->{$param};
    }

}

sub db_data {
    my ( $tag, $options ) = @_;
    my $sth = $dbh->prepare( $Sql{$tag} );
    my $rv  = $sth->execute();
    warn DBI->errstr if $rv < 0;
    my $data;
    if ( exists $options->{hashref} ) {
        $data = $sth->fetchall_hashref( $options->{hashref} );
    }
    else {
        $data = $sth->fetchall_arrayref();
    }
    $sth->finish();
    return $data;
}

sub pause_for {
    my ($seconds) = @_;
    die "can't pause for $seconds seconds, not a positive integer!\n"
      unless $seconds =~ m/\d+/;
    print "==> pausing for $seconds seconds...\n";
    sleep $seconds;
}

#### Init
my $force = '';
my $help  = '';
GetOptions(
    'force' => \$force,
    'help'  => sub { print "Usage: $0 [--force]\n"; exit 0; }
);
my $interval = 140;    # around every day

# Sql statements

$Sql{'last_block'} =
qq/select timestamp, block, no_of_coins from blocks where timestamp < datetime('now') order by timestamp desc limit 1/;
$Sql{'last_3'} =
qq/select julianday(timestamp), block, no_of_coins from blocks where timestamp < date('now') order by timestamp desc limit 3/;
$Sql{'halvings'} =
qq/select strftime('%s',timestamp),block,no_of_coins from blocks where timestamp >= datetime('now')/;
$Sql{'list'} =
  qq/select julianday(timestamp) as ts, block,no_of_coins as coins from blocks/;
#### Main code

$dbh = DBI->connect( $dsn, $user, $pass, { RaiseError => 1 } )
  or die $DBI::errstr;
my $last_block = db_data('last_block');
my $target     = $last_block->[0]->[1] + $interval;

my $last_3         = db_data('last_3');
my $block_delta    = $last_3->[0]->[1] - $last_3->[2]->[1];
my $day_delta      = $last_3->[0]->[0] - $last_3->[2]->[0];
my $blocks_per_day = $block_delta / $day_delta;
printf( " Avg blocks per day: %.2f (based on last 3 entries)\n",
    $blocks_per_day );

print "Getting current block count...\n";
my $json = web_data( 'bitcoin/blocks?q=size(10..)', 'data' );
die "Value returned from web service is not defined!" unless defined $json;

# we want the first element
my $latest_id = $json->[0]->{id};
my $latest_time = $json->[0]->{median_time};


#print Dumper $json;


if ( $latest_id >= $target or $force ) {
    if ($force) {
        print "Force option, proceeding with update\n";
    }
    else {
        print "We have newer mined block $latest_id than target block $target...\n";
    }
    my $current_block = $latest_id;
    my $dt = $strp->parse_datetime($latest_time);
#    my ( $block_hash, $block_time, $dt ) = ( undef, undef, undef );
#    $block_hash = web_data( "block-index/$current_block", 'blockHash' );
#    die "can't get data for $current_block!" unless defined $block_hash;

#    pause_for(4);
#    $block_time = web_data( "block/$block_hash", 'time' );
#    $dt = DateTime->from_epoch( epoch => $block_time );

    # insert into DB

    $sth = $dbh->prepare(
        "insert into blocks (timestamp, block, no_of_coins) values (?,?,?)");
    print "Found block $current_block at time: ",
      $latest_time, "\n";
    print ' ' x 12 . "Number of coins for block is: ",
      coins_per_block($current_block), "\n";
    print "Inserting into DB...\n";

    $sth->execute( $latest_time,
        $current_block, coins_per_block($current_block) );
    $sth->finish;

    # update the dates for next halvings
    $block_delta    = $current_block - $last_3->[1]->[1];
    $day_delta      = $dt->jd() - $last_3->[1]->[0];
    $blocks_per_day = $block_delta / $day_delta;
    printf( "Blocks per day based on last 2 entries: %.2f \n",$blocks_per_day);

    my $halvings = db_data('halvings');
    foreach my $halving ( @{$halvings} ) {
        my ( $ts, $halving_block, $coins ) = @{$halving};
        next unless $halving_block % 210_000 == 0;

        # compute the timestamp based on current rate and number of blocks left
        my $blocks_left   = $halving_block - $current_block;
        my $standard_rate = 144;
        my $eta = time() + ( $blocks_left / $standard_rate ) * 24 * 3600;
        if ( $eta != $ts ) {
            print "New ETA for block $halving_block calculated: ",
              scalar gmtime($eta), "\n";
            print ' ' x 23 . "(Old ETA was: ", scalar gmtime($ts), ")\n";
            print ' ' x 31 . "Diff: ", int( $eta - $ts ), "s\n";

            #	    next unless $update_future == 1;
            print "updating date for $halving_block\n";
            my $dt = DateTime->from_epoch( epoch => $eta );
            $sth = $dbh->prepare("update blocks set timestamp=? where block=?");
            my $rv = $sth->execute( $dt->strftime('%Y-%m-%d %H:%M:%S'),
                $halving_block, );
            warn DBI->errstr if $rv < 0;
            $sth->finish;
        }
    }

}
else {
    my $diff = $target - $json;
    print "Latest stored block: " . $last_block->[0]->[1] . "\n";
    print "       Target block: $target\n";
    print "   Last mined block: $latest_id\n";
    my $eta = time() + ( $diff / $blocks_per_day ) * 24 * 3600;
    print "   Remaining blocks: $diff\n";
    print "Target block ETA on ", scalar gmtime($eta), " UTC\n";
}
$dbh->disconnect;
exit 0;
