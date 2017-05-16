#!/usr/bin/perl
use strict;
use warnings;
use DBI;
use Statistics::LineFit;

my $driver = 'SQLite';
my $database = '/home/www/gerikson.com/cgi-bin/data/historical-prices.db';
my $dsn = "DBI:$driver:dbname=$database";
#print "$dsn\n";
#exit 0;
my ($user, $pass) = ('','');

my $dbh = DBI->connect($dsn, $user, $pass, {RaiseError=>1}) or die $DBI::errstr;

# get the data
my $sth = $dbh->prepare(qq/select julianday(timestamp), average from history where volume is not null and timestamp <= date('now', '-3 day')/);
my @X; my @Y; my @Z;
$sth->execute;
while  ( my @r = $sth->fetchrow_array) {
    push @X, $r[0];
    push @Y, log($r[1]);
    push @Z, $r[1];
}
$sth->finish();
my $start_date = $X[0];
my @X_0 = map { $_- $start_date } @X;
my $exponential =Statistics::LineFit->new();
$exponential->setData(\@X_0, \@Y) or die "Invalid regression data\n";
my ($e_intercept, $e_slope) = $exponential->coefficients();

my $linear = Statistics::LineFit->new();
$linear->setData(\@X,\@Z) or die "Invalid regression data\n";
my ($l_intercept, $l_slope) = $linear->coefficients();

my @x; my @y;
#$sth = $dbh->prepare(qq/select julianday(timestamp), average from history where timestamp > '2015-01-14'/);
# $sth = $dbh->prepare(qq/select julianday(timestamp), average from history where timestamp > '2013-11-29'/);
$sth = $dbh->prepare(qq/select julianday(timestamp), average from history where timestamp > date('now', '-90 day')/);
$sth->execute();
while (my @r = $sth->fetchrow_array ){
    push @x, $r[0]; push @y, $r[1];
}

$sth->finish;

my $short_term = Statistics::LineFit->new();
$short_term->setData(\@x, \@y) or die "Invalid regression data\n";
my ($s_intercept, $s_slope) = $short_term->coefficients();

printf("Exponential: slope: %.06f, intercept: %.06f\n",
       $e_slope, $e_intercept);
printf("     Linear: slope: %.06f, intercept: %.06f\n",
      $l_slope, $l_intercept);
printf("     30 day: slope: %.06f, intercept: %.06f\n",
      $s_slope,  $s_intercept);
#exit 0;
my $rv = $dbh->do(qq/insert into coefficients (timestamp, intercept_exp, slope_exp, intercept_lin, slope_lin, intercept_30d, slope_30d) values (datetime('now'), ?,?,?,?,?,?)/, undef,
	      $e_intercept, $e_slope,
	      $l_intercept, $l_slope,
	      $s_intercept, $s_slope);
warn $DBI::errstr if $rv<0;

__END__
$rv = $dbh->do("insert into ranges (timestamp_1, average_1, timestamp_2, average_2) values ( ?, ? ,?, ?)", undef,$range->[0]->[0],
		    $range->[0]->[1],
		    $range->[1]->[0],
		    $range->[1]->[1]) ;
    warn $DBI::errstr if $rv<0;


#print "Best fit for log data is a line with intercept: $intercept and slope: $slope\n";

