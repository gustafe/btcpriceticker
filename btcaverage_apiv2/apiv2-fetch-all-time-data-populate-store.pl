#!/usr/bin/perl
use strict;
use warnings;
use Text::CSV;
use BTCtracker qw/get_dbh get_ua/;

my $dbh = get_dbh();
my $api_url
    = 'https://apiv2.bitcoinaverage.com/indices/global/history/BTCUSD?period=alltime&format=csv';
my $fh;
my $csv;
my $ua       = get_ua();
my $response = $ua->get($api_url);

if ( !$response->is_success ) {
    die $response->status_line;
} else {
    my $data = $response->decoded_content;

    open( $fh, '<', \$data )
        || die "couldn't open scalar variable as file: $!";

    $csv      = Text::CSV->new( { binary => 1 } );
    my $inserted = 0;
    my $skipped  = 0;

    #my ($timestamp, $high, $low, $average, $volume );
    while ( my $row = $csv->getline($fh) ) {

        my ( $timestamp, $high, $low, $average, $volume )
            = @{$row}[ 0, 1, 2, 3, 4 ];
        next unless ( $timestamp =~ m/\d{4}-\d{2}-\d{2}/ );

        # do we have this data?
        my $sth
            = $dbh->prepare(
'select timestamp from history where timestamp = ? and volume is not null' );
        $sth->execute($timestamp);
        next if ( $sth->fetchrow_array );

        my $insert = 0;
        my $update = 0;
        warn '==> ', join( '|', @{$row} ), "\n";
        $insert = $dbh->do(
'insert into history (timestamp, high, low, average, volume) values (?,?,?,?,?)',
            undef, $timestamp, $high, $low, $average, $volume );
        if ( $dbh->err ) {    # insert failed
            $update = $dbh->do(
q{update history set high=?, low=?, average=?, volume=? where timestamp=?},
                undef, $high, $low, $average, $volume, $timestamp );
            warn $DBI::errstr if ( $update < 0 );
        }

        $inserted += ( $insert ? $insert : 0 + $update ? $update : 0 );

        #    print "*" unless $inserted%10;
        #    print " $inserted\n" unless $inserted%500;
    }
    warn "==> Skipped: $skipped, Inserted: $inserted\n";
}

close $fh;
$csv->eof or $csv->error_diag();
$dbh->disconnect() or warn $DBI::errstr;
