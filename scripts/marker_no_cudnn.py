#!/usr/bin/env python3
"""Wrapper around marker_single that disables cuDNN before import.

Needed on Blackwell (RTX 5080) where cuDNN 9.19 triggers an init bug.
On macOS this is a harmless no-op.
"""
import sys

import torch

torch.backends.cudnn.enabled = False

from marker.scripts.convert_single import convert_single_cli

if __name__ == "__main__":
    convert_single_cli.main(args=sys.argv[1:], prog_name="marker_single")
