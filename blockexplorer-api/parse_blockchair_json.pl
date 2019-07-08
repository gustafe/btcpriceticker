#! /usr/bin/env perl
use Modern::Perl '2015';
###

use JSON;


open my $fh, '<', './blockchair.json' or die;
$/=undef;
my $data = <$fh>;
close $fh;
#say $data;
my $json = decode_json( $data);

foreach my $el (@{$json->{data}}) {
    say join("\t", $el->{median_time}, $el->{id});
}
