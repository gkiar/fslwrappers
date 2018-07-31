#!/usr/bin/env python

from eddy_driver import hcpparser
import boutiques.creator as bc


newDescriptor = bc.CreateDescriptor(hcpparser(),
                                    execname="python eddy_driver.py")
newDescriptor.save("eddy_driver.json")
