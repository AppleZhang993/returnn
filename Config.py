#! /usr/bin/python2.7

__author__ = "Patrick Doetsch"
__copyright__ = "Copyright 2014"
__credits__ = ["Patrick Doetsch", "Paul Voigtlaender"]
__license__ = "GPL"
__version__ = "0.9"
__maintainer__ = "Patrick Doetsch"
__email__ = "doetsch@i6.informatik.rwth-aachen.de"


class Config:
  def __init__(self):
    self.dict = {}; """ :type: dict[str, list[str]] """
    self.network_topology_json = None; """ :type: str | None """

  def load_file(self, filename):
    for line in open(filename).readlines():
      if "#" in line:  # Strip away comment.
        line = line[:line.index("#")]
      line = line.strip()
      if not line:
        continue
      line = line.split(None, 1)
      assert len(line) == 2, "unable to parse config line: %r" % line
      self.add_line(key=line[0], value=line[1])

  def add_line(self, key, value):
    if value.find(',') > 0:
      value = value.split(',')
    else:
      value = [value]
    self.dict[key] = value

  def has(self, key):
    return key in self.dict

  def set(self, key, value):
    """
    :type key: str
    :type value: list[str] | str | int | float | bool
    """
    if not isinstance(value, (list, tuple)): value = [value]
    value = [str(v) for v in value]
    self.dict[key] = value

  def value(self, key, default, index=None):
    """
    :type key: str
    :type default: T
    :type index: int | None
    :rtype: str | T
    """
    if key not in self.dict:
      return default
    l = self.dict[key]
    if index is None:
      return ",".join(l)
    else:
      return l[index]

  def int(self, key, default, index=0):
    return int(self.value(key, default, index))

  def bool(self, key, default, index=0):
    if key not in self.dict:
      return default
    v = str(self.value(key, None, index)).lower()
    if v == "true" or v == 'True' or v == "1":
      return True
    if v == "false" or v == 'False' or v == "0":
      return False
    assert v == "", "invalid bool value for %s: %s" % (key, v)
    return default

  def float(self, key, default, index=0):
    return float(self.value(key, default, index))

  def list(self, key, default=None):
    """
    :type key: str
    :type default: T
    :rtype: list[str] | T
    """
    if default is None: default = []
    if key not in self.dict:
      return default
    return self.dict[key]

  def int_list(self, key, default=None):
    if default is None: default = []
    return [int(x) for x in self.list(key, default)]

  def float_list(self, key, default=None):
    if default is None: default = []
    return [float(x) for x in self.list(key, default)]

  def int_pair(self, key, default=None):
    if default is None: default = (0, 0)
    if not self.has(key): return default
    value = self.value(key, '')
    if ':' in value:
      return int(value.split(':')[0]), int(value.split(':')[1])
    else:
      return int(value), int(value)
