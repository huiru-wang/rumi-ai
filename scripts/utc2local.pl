#!/usr/bin/perl -p
use POSIX qw(strftime);
use Time::Local qw(timegm);
s/(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})\.?(\d*)Z/
  my $epoch = timegm($6,$5,$4,$3,$2-1,$1-1900);
  strftime("%Y-%m-%dT%H:%M:%S", localtime($epoch)) . ($7 ? ".$7" : "")
/ge;
