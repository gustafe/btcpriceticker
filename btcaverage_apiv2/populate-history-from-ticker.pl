#! /usr/bin/env perl
use Modern::Perl '2015';
use BTCtracker qw/get_dbh get_ua/;
use DateTime;
use DateTime::Format::Strptime;
use Data::Dumper;
###

my $debug        = 0;
my $dry_run = 0;
my $get_date_sql = 'select max(timestamp) from history';
my $get_ticker_data =
"select max(last), min(last), avg(last), avg(volume) from ticker where timestamp >= ? and timestamp <= ?";
my $update_history =
"insert into history ( timestamp, high, low, average, volume ) values ( ?, ?, ?, ?, ? )";

my $strp = DateTime::Format::Strptime->new(
    pattern  => '%Y-%m-%d %H:%M:%S',
    on_error => 'croak'
);

my $dbh            = get_dbh();
my $last_read_date = $dbh->selectall_arrayref($get_date_sql);
my $read_sth       = $dbh->prepare($get_ticker_data);
my $updt_sth       = $dbh->prepare($update_history);

my $start_dt = $strp->parse_datetime( $last_read_date->[0]->[0] );

my $end_dt = DateTime->today();

my $step_dt = $start_dt->add( days => 1 );

say join( " ", qw(ts high low average volume) ) if $debug ;

do {

    my $rv = $read_sth->execute( $step_dt->ymd . ' 00:00:00',
        $step_dt->ymd . ' 23:59:59' );

    my $ary_ref = $read_sth->fetchall_arrayref;
    my $row     = $ary_ref->[0];                  # only one row returned
    my ( $high, $low, $average, $volume ) = @$row;
    my @bind_params = (
        $step_dt->ymd . ' 00:00:00',
        $high, $low, sprintf( "%.02f", $average ), $volume
    );

        say join( " ",
            $step_dt->ymd . ' 00:00:00',
            $high, $low, sprintf( "%.02f", $average ), $volume );


        $updt_sth->execute(@bind_params) unless $dry_run;


    #    say Dumper $ary_ref;
    $step_dt = $step_dt->add( days => 1 );
} until ( $step_dt == $end_dt );
