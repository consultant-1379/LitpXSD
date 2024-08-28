#!/bin/sh

echo "Expand deps called"
pushd $1
echo "cd to target deps dir"
for i in *.rpm ; do rpm2cpio $i | cpio -idmv ; done

popd
exit
