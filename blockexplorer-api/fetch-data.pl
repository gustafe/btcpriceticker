#!/usr/bin/perl
use strict;
use warnings;
use DBI;
use Text::CSV;
use LWP::Simple;
use JSON;
use POSIX::strptime;
use POSIX qw(strftime);
use DateTime;

my $base_url = 'https://blockexplorer.com/api';

sub coins_per_block {
    my ( $blocks ) = @_;
    return undef unless $blocks > 0;
    my $reward = 50;
    my $period = 210_000;
    my $diff = 0;
    my $coins = 0;

    while ( $diff >= 0 ) {
	$diff = $blocks - $period;
	$coins += ( $diff < 0 ? $blocks * $reward : $period * $reward );
	$blocks = $diff;
#	$period = $period * 2;
	$reward = $reward / 2;
    }
    return $coins;
}


sub get_data {
    my ( $api_string, $param ) = @_;
    my $json = get ( "$base_url/$api_string" );
    return undef unless defined $json;
    my $info = decode_json( $json );
#    foreach my $key ( sort keys %{$info} ) {
#	print "$key : $info->{$key}\n";
#    }
    
    return $info->{$param};
}

my $block = shift @ARGV || undef;
if ( defined $block and $block !~ /\d+/ ) {
    die "Input $block is not positive integer\n"
}

my $current_block = defined $block? $block : get_data( 'status?q=getBlockCount', 'blockcount' );
my $block_hash =get_data( "block-index/$current_block", 'blockHash');
die "can't get data for $current_block!" unless defined $block_hash;
my $block_time = get_data( "block/$block_hash", 'time' );
my $dt = DateTime->from_epoch(epoch=>$block_time);
my $ts = $dt->strftime("%Y-%m-%d %H:%M:%S");
my $coins =coins_per_block($current_block);
print join("\t",$block_time, $ts, $current_block, $coins),"\n";
printf("insert into blocks values (\'%s\',%d,%d);\n",
       $ts, $current_block, $coins);
printf("update blocks set timestamp='\%s\' where block = %d;\n",
       $ts, $current_block);
#Time: ", scalar gmtime( $block_time ), " UTC\n";

__END__
#my $current_block_call = "$base_url/status?q=getBlockCount";
my $current_block_json = get ( "$base_url/status?q=getBlockCount" );
my $current_block_info = decode_json( $current_block_json );
my $current_block = $current_block_info->{'blockcount'};
