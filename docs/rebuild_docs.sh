# script to rebuild documentation aftter removing intermediates
rm -r build
rm -r source/reference/generated/*
make html

