
# start test like this:  nosetests-2.7  tests/test_TFEngine.py


import logging
logging.getLogger('tensorflow').disabled = True
import tensorflow as tf
import sys
sys.path += ["."]  # Python 3 hack
from TFEngine import *
import Util
import TFUtil
TFUtil.debugRegisterBetterRepr()
from Config import Config
from nose.tools import assert_equal, assert_is_instance
import numpy
import numpy.testing
import os
from pprint import pprint
import better_exchook
better_exchook.replace_traceback_format_tb()
from Log import log
log.initialize(verbosity=[5])

session = tf.InteractiveSession()


def test_DataProvider():
  """
  :param Dataset.Dataset dataset:
  :param int seq_idx:
  :param str|None output_layer_name: e.g. "output". if not set, will read from config "forward_output_layer"
  :return: numpy array, output in time major format (time,batch,dim)
  :rtype: numpy.ndarray
  """
  from GeneratingDataset import DummyDataset
  seq_len = 5
  n_data_dim = 2
  n_classes_dim = 3
  dataset = DummyDataset(input_dim=n_data_dim, output_dim=n_classes_dim, num_seqs=2, seq_len=seq_len)
  dataset.init_seq_order(epoch=1)

  extern_data = ExternData()
  extern_data.init_from_dataset(dataset)

  # No Runner instance here but a very simplified version of Runner.run().
  # First we need a custom DataProvider with a custom BatchSetGenerator
  # which will yield only one single batch for the provided sequence idx.
  seq_idx = 0
  n_batch = 1
  batch = Batch()
  batch.add_frames(seq_idx=seq_idx, seq_start_frame=0, length=dataset.get_seq_length(seq_idx))
  batch_generator = iter([batch])
  batches = BatchSetGenerator(dataset, generator=batch_generator)
  from TFDataPipeline import FeedDictDataProvider
  data_provider = FeedDictDataProvider(
    tf_session=session, extern_data=extern_data,
    data_keys=["data", "classes"],
    dataset=dataset, batches=batches)

  feed_dict = data_provider.get_feed_dict(single_threaded=True)
  print(feed_dict)
  assert_is_instance(feed_dict, dict)
  assert extern_data.data["data"].placeholder in feed_dict
  assert extern_data.data["data"].size_placeholder[0] in feed_dict
  assert extern_data.data["classes"].placeholder in feed_dict
  assert extern_data.data["classes"].size_placeholder[0] in feed_dict
  data = feed_dict[extern_data.data["data"].placeholder]
  data_size = feed_dict[extern_data.data["data"].size_placeholder[0]]
  classes = feed_dict[extern_data.data["classes"].placeholder]
  classes_size = feed_dict[extern_data.data["classes"].size_placeholder[0]]
  assert_is_instance(data, numpy.ndarray)
  assert_is_instance(data_size, numpy.ndarray)
  assert_is_instance(classes, numpy.ndarray)
  assert_is_instance(classes_size, numpy.ndarray)
  assert_equal(data.shape, (n_batch, seq_len, n_data_dim))
  assert_equal(data_size.shape, (n_batch,))
  assert_equal(classes.shape, (n_batch, seq_len))
  assert_equal(classes_size.shape, (n_batch,))
  assert_equal(list(data_size), [seq_len])
  assert_equal(list(classes_size), [seq_len])
  numpy.testing.assert_almost_equal(list(data[0, 0]), [-0.5, -0.4])
  numpy.testing.assert_almost_equal(list(data[0, -1]), [0.3, 0.4])
  assert_equal(classes.tolist(), [[1, 2, 0, 1, 2]])


def test_engine_train():
  from GeneratingDataset import DummyDataset
  seq_len = 5
  n_data_dim = 2
  n_classes_dim = 3
  train_data = DummyDataset(input_dim=n_data_dim, output_dim=n_classes_dim, num_seqs=4, seq_len=seq_len)
  train_data.init_seq_order(epoch=1)
  cv_data = DummyDataset(input_dim=n_data_dim, output_dim=n_classes_dim, num_seqs=2, seq_len=seq_len)
  cv_data.init_seq_order(epoch=1)

  config = Config()
  config.update({
    "model": "/tmp/model",
    "num_outputs": n_classes_dim,
    "num_inputs": n_data_dim,
    "network": {"output": {"class": "softmax", "loss": "ce"}},
    "start_epoch": 1,
    "num_epochs": 2
  })
  engine = Engine(config=config)
  engine.init_train_from_config(config=config, train_data=train_data, dev_data=cv_data, eval_data=None)
  engine.train()


def test_engine_analyze():
  from GeneratingDataset import DummyDataset
  seq_len = 5
  n_data_dim = 2
  n_classes_dim = 3
  dataset = DummyDataset(input_dim=n_data_dim, output_dim=n_classes_dim, num_seqs=2, seq_len=seq_len)
  dataset.init_seq_order(epoch=1)

  config = Config()
  config.update({
    "model": "/tmp/model",
    "num_outputs": n_classes_dim,
    "num_inputs": n_data_dim,
    "network": {"output": {"class": "softmax", "loss": "ce"}},
    "sil_label_idx": 0,
  })
  engine = Engine(config=config)
  # Normally init_network_from_config but that requires an existing network model.
  # engine.init_network_from_config(config=config)
  engine.init_train_from_config(config=config, train_data=dataset, dev_data=None, eval_data=None)

  engine.analyze(data=dataset, statistics=None)


def test_engine_forward_single():
  from GeneratingDataset import DummyDataset
  seq_len = 5
  n_data_dim = 2
  n_classes_dim = 3
  dataset = DummyDataset(input_dim=n_data_dim, output_dim=n_classes_dim, num_seqs=2, seq_len=seq_len)
  dataset.init_seq_order(epoch=1)

  config = Config()
  config.update({
    "model": "/tmp/model",
    "num_outputs": n_classes_dim,
    "num_inputs": n_data_dim,
    "network": {"output": {"class": "softmax", "loss": "ce"}}
  })
  engine = Engine(config=config)
  engine.init_train_from_config(config=config, train_data=dataset, dev_data=None, eval_data=None)

  engine.forward_single(dataset=dataset, seq_idx=0)


def test_engine_forward_to_hdf():
  from GeneratingDataset import DummyDataset
  import tempfile
  output_file = tempfile.mktemp(suffix=".hdf", prefix="nose-tf-forward")
  seq_len = 5
  n_data_dim = 2
  n_classes_dim = 3
  num_seqs = 20
  dataset = DummyDataset(input_dim=n_data_dim, output_dim=n_classes_dim,
                         num_seqs=num_seqs, seq_len=seq_len)
  dataset.init_seq_order(epoch=1)

  config = Config()
  config.update({
    "model": "/tmp/model",
    "num_outputs": n_classes_dim,
    "num_inputs": n_data_dim,
    "network": {"output": {"class": "softmax", "loss": "ce"}},
    "output_file": output_file,
  })

  engine = Engine(config=config)
  engine.init_train_from_config(config=config, train_data=dataset, dev_data=None, eval_data=None,)

  engine.forward_to_hdf(data=dataset, output_file=output_file, batch_size=5)
  assert os.path.exists(output_file)
  import h5py
  with h5py.File(output_file, 'r') as f:
    assert f['inputs'].shape == (seq_len*num_seqs, n_classes_dim)
    assert f['seqLengths'].shape == (num_seqs,2)
    assert f['seqTags'].shape == (num_seqs,)
    assert f.attrs['inputPattSize'] == n_data_dim
    assert f.attrs['numSeqs'] == num_seqs
    assert f.attrs['numTimesteps'] == seq_len * num_seqs

  from HDFDataset import HDFDataset
  ds = HDFDataset()
  ds.add_file(output_file)

  assert_equal(ds.num_inputs, n_classes_dim) # forwarded input is network output
  assert_equal(ds.get_num_timesteps(), seq_len*num_seqs)
  assert_equal(ds.num_seqs, num_seqs)

  os.remove(output_file)


def test_engine_rec_subnet_count():
  from GeneratingDataset import DummyDataset
  seq_len = 5
  # The dataset is actually not used.
  n_data_dim = 2
  n_classes_dim = 3
  dataset = DummyDataset(input_dim=n_data_dim, output_dim=n_classes_dim, num_seqs=2, seq_len=seq_len)
  dataset.init_seq_order(epoch=1)

  config = Config()
  config.update({
    "model": "/tmp/model",
    "num_outputs": n_classes_dim,
    "num_inputs": n_data_dim,
    "network": {
      "output": {
        "class": "rec",
        "from": ["data"],  # actually not used, except that it defines the length
        "unit": {
        "output": {
          "class": "activation", "activation": "identity + 1",
          "from": ["prev:output"], "initial_output": 0,  # note: initial output is for t == -1
          "out_type": {"dim": 1, "dtype": "int32"}}
      }}}
  })
  engine = Engine(config=config)
  engine.init_train_from_config(config=config, train_data=dataset, dev_data=None, eval_data=None)

  out = engine.forward_single(dataset=dataset, seq_idx=0)
  assert_equal(out.shape, (seq_len, 1))
  assert_equal(out.dtype, numpy.int32)
  assert_equal(list(out[:,0]), list(range(1, seq_len + 1)))


def test_engine_search():
  from GeneratingDataset import DummyDataset
  seq_len = 5
  n_data_dim = 2
  n_classes_dim = 3
  dataset = DummyDataset(input_dim=n_data_dim, output_dim=n_classes_dim, num_seqs=2, seq_len=seq_len)
  dataset.init_seq_order(epoch=1)

  config = Config()
  config.update({
    "model": "/tmp/model",
    "batch_size": 5000,
    "num_outputs": n_classes_dim,
    "num_inputs": n_data_dim,
    "network": {
      "output": {"class": "rec", "from": [], "max_seq_len": 10, "target": "classes", "unit": {
        "prob": {"class": "softmax", "from": ["prev:output"], "loss": "ce", "target": "classes"},
        "output": {"class": "choice", "beam_size": 4, "from": ["prob"], "target": "classes", "initial_output": 0},
        "end": {"class": "compare", "from": ["output"], "value": 0}
      }},
      "decision": {"class": "decide", "from": ["output"], "loss": "edit_distance"}
    }
  })
  engine = Engine(config=config)
  # Normally init_network can be used. We only do init_train here to randomly initialize the network.
  engine.init_train_from_config(config=config, train_data=dataset, dev_data=None, eval_data=None)
  print("network:")
  pprint(engine.network.layers)
  assert "output" in engine.network.layers
  assert "decision" in engine.network.layers

  engine.search(dataset=dataset)
  print("error keys:")
  pprint(engine.network.error_by_layer)
  assert engine.network.total_objective is not None
  assert "decision" in engine.network.error_by_layer

  engine.finalize()


def test_engine_search_attention():
  from GeneratingDataset import DummyDataset
  seq_len = 5
  n_data_dim = 2
  n_classes_dim = 3
  dataset = DummyDataset(input_dim=n_data_dim, output_dim=n_classes_dim, num_seqs=2, seq_len=seq_len)
  dataset.init_seq_order(epoch=1)
  print("Hello search!")

  config = Config()
  config.update({
    "model": "/tmp/model",
    "batch_size": 5000,
    "max_seqs": 2,
    "num_outputs": n_classes_dim,
    "num_inputs": n_data_dim,
    "network": {
      "encoder": {"class": "linear", "activation": "tanh", "n_out": 5},
      "output": {"class": "rec", "from": [], "unit": {
        'output': {'class': 'choice', 'target': 'classes', 'beam_size': 4, 'from': ["output_prob"]},
        "end": {"class": "compare", "from": ["output"], "value": 0},
        'orth_embed': {'class': 'linear', 'activation': None, 'from': ['output'], "n_out": 7},
        "s": {"class": "rnn_cell", "unit": "LSTMBlock", "from": ["prev:c", "prev:orth_embed"], "n_out": 7},
        "c_in": {"class": "linear", "activation": "tanh", "from": ["s", "prev:orth_embed"], "n_out": 5},
        "c": {"class": "dot_attention", "from": ["c_in"], "base": "base:encoder", "base_ctx": "base:encoder"},
        "output_prob": {"class": "softmax", "from": ["prev:s", "c"], "target": "classes", "loss": "ce"}
      }, "target": "classes", "max_seq_len": 10},
      "decision": {"class": "decide", "from": ["output"], "loss": "edit_distance"}
    }})
  engine = Engine(config=config)
  print("Init network...")
  engine.start_epoch = 1
  engine.use_dynamic_train_flag = False
  engine.use_search_flag = True
  engine.init_network_from_config(config)
  print("network:")
  pprint(engine.network.layers)
  assert "output" in engine.network.layers
  assert "decision" in engine.network.layers

  print("Search...")
  engine.search(dataset=dataset)
  print("error keys:")
  pprint(engine.network.error_by_layer)
  assert engine.network.total_objective is not None
  assert "decision" in engine.network.error_by_layer

  engine.finalize()


def test_rec_subnet_train_t3b():
  beam_size = 2
  network = {
    "data_embed": {"class": "linear", "activation": None, "with_bias": False, "n_out": 6},
    "lstm0_fw" : { "class": "rec", "unit": "lstmp", "n_out" : 6, "dropout": 0.1, "L2": 0.01, "direction": 1, "from": ["data_embed"] },
    "lstm0_bw" : { "class": "rec", "unit": "lstmp", "n_out" : 6, "dropout": 0.1, "L2": 0.01, "direction": -1, "from": ["data_embed"] },
    "lstm1_fw" : { "class": "rec", "unit": "lstmp", "n_out" : 6, "dropout": 0.1, "L2": 0.01, "direction": 1, "from": ["data_embed"] },
    "lstm1_bw" : { "class": "rec", "unit": "lstmp", "n_out" : 6, "dropout": 0.1, "L2": 0.01, "direction": -1, "from": ["data_embed"] },
    "encoder": {"class": "copy", "from": ["lstm1_fw", "lstm1_bw"]},
    "enc_ctx": {"class": "linear", "activation": None, "with_bias": False, "from": ["encoder"], "n_out": 5},
    "enc_emb": {"class": "copy", "from": ["enc_ctx"]},

    "output": {"class": "rec", "from": [], "unit": {
      'output': {'class': 'choice', 'target': 'classes', 'beam_size': beam_size, 'from': ["output_prob"]},
      "end": {"class": "compare", "from": ["output"], "value": 0},
      'orth_embed': {'class': 'linear', 'activation': None, "with_bias": False, 'from': ['output'], "n_out": 6},
      "s_in": {"class": "linear", "activation": "tanh", "from": ["prev:c", "prev:orth_embed"], "n_out": 5},
      "s": {"class": "rnn_cell", "unit": "LSTMBlock", "from": ["s_in"], "n_out": 5},  # h_t
      "c_in": {"class": "copy", "from": ["s"]},
      "c": {"class": "dot_attention", "from": ["c_in"], "base": "base:enc_emb", "base_ctx": "base:enc_ctx"},
      "t1": {"class": "linear", "activation": "tanh", "from": ["c", "s"], "n_out": 6},
      "t2": {"class": "linear", "activation": "tanh", "from": ["t1"], "n_out": 6},
      "t3": {"class": "linear", "activation": "tanh", "from": ["t2"], "n_out": 6},
      "output_prob": {"class": "softmax", "from": ["t3"], "target": "classes", "loss": "ce"}
    }, "target": "classes", "max_seq_len": 75},

    "decision": {
      "class": "decide", "from": ["output"], "loss": "edit_distance", "target": "classes",
      "loss_opts": {
        "debug_print": True
      }
    }
  }

  from GeneratingDataset import DummyDataset
  seq_len = 5
  n_data_dim = 2
  n_classes_dim = 3
  train_data = DummyDataset(input_dim=n_data_dim, output_dim=n_classes_dim, num_seqs=4, seq_len=seq_len)
  train_data.init_seq_order(epoch=1)
  cv_data = DummyDataset(input_dim=n_data_dim, output_dim=n_classes_dim, num_seqs=2, seq_len=seq_len)
  cv_data.init_seq_order(epoch=1)

  config = Config()
  config.update({
    "model": "/tmp/model",
    "num_outputs": n_classes_dim,
    "num_inputs": n_data_dim,
    "network": network,
    "start_epoch": 1,
    "num_epochs": 2,
    "batch_size": 10,
    "nadam": True,
    "learning_rate": 0.01,
  })
  engine = Engine(config=config)
  engine.init_train_from_config(config=config, train_data=train_data, dev_data=cv_data, eval_data=None)
  engine.train()


def test_rec_subnet_train_t3d():
  beam_size = 2
  network = {
    "data_embed": {"class": "linear", "activation": None, "with_bias": False, "n_out": 6},
    "lstm0_fw" : { "class": "rec", "unit": "nativelstm2", "n_out" : 5, "dropout": 0.1, "L2": 0.01, "direction": 1, "from": ["data_embed"] },
    "lstm0_bw" : { "class": "rec", "unit": "nativelstm2", "n_out" : 5, "dropout": 0.1, "L2": 0.01, "direction": -1, "from": ["data_embed"] },
    "encoder_state": {"class": "get_last_hidden_state", "from": ["lstm0_fw", "lstm0_bw"], "n_out": 2*5},
    "enc_state_embed": {"class": "linear", "activation": None, "with_bias": False, "from": ["encoder_state"], "n_out": 5},
    "encoder": {"class": "copy", "from": ["lstm0_fw", "lstm0_bw"]},
    "enc_ctx": {"class": "linear", "activation": None, "with_bias": False, "from": ["encoder"], "n_out": 5},
    "enc_emb": {"class": "copy", "from": ["enc_ctx"]},

    "output": {"class": "rec", "from": [], "unit": {
      'output': {'class': 'choice', 'target': 'classes', 'beam_size': beam_size, 'from': ["output_prob"]},
      "end": {"class": "compare", "from": ["output"], "value": 0},
      'orth_embed': {'class': 'linear', 'activation': None, "with_bias": False, 'from': ['output'], "n_out": 6},
      "s_in": {"class": "linear", "activation": "tanh", "from": ["prev:c", "prev:orth_embed"], "n_out": 5},
      "s": {"class": "rnn_cell", "unit": "LSTMBlock", "from": ["s_in"], "initial_state": {"c": "base:enc_state_embed", "h": 0}, "n_out": 5},  # h_t
      "c_in": {"class": "copy", "from": ["s"]},
      "c": {"class": "dot_attention", "from": ["c_in"], "base": "base:enc_emb", "base_ctx": "base:enc_ctx",
      "energy_factor": 1.0/numpy.sqrt(5)},
      "att": {"class": "linear", "activation": "tanh", "from": ["c", "s"], "n_out": 6},  # \tilde h
      "output_prob": {"class": "softmax", "from": ["att"], "target": "classes", "loss": "ce"}
    }, "target": "classes", "max_seq_len": 75},
  }

  from GeneratingDataset import DummyDataset
  seq_len = 5
  n_data_dim = 2
  n_classes_dim = 3
  train_data = DummyDataset(input_dim=n_data_dim, output_dim=n_classes_dim, num_seqs=4, seq_len=seq_len)
  train_data.init_seq_order(epoch=1)
  cv_data = DummyDataset(input_dim=n_data_dim, output_dim=n_classes_dim, num_seqs=2, seq_len=seq_len)
  cv_data.init_seq_order(epoch=1)

  config = Config()
  config.update({
    "model": "/tmp/model",
    "num_outputs": n_classes_dim,
    "num_inputs": n_data_dim,
    "network": network,
    "start_epoch": 1,
    "num_epochs": 2,
    "batch_size": 10,
    "nadam": True,
    "learning_rate": 0.01,
  })
  engine = Engine(config=config)
  engine.init_train_from_config(config=config, train_data=train_data, dev_data=cv_data, eval_data=None)
  engine.train()


def test_rec_subnet_train_t3d_simple():
  beam_size = 2
  network = {
    "encoder": {"class": "linear", "activation": "tanh", "n_out": 5},
    "output": {"class": "rec", "from": [], "unit": {
      'output': {'class': 'choice', 'target': 'classes', 'beam_size': beam_size, 'from': ["output_prob"]},
      "end": {"class": "compare", "from": ["output"], "value": 0},
      'orth_embed': {'class': 'linear', 'activation': None, "with_bias": False, 'from': ['output'], "n_out": 6},
      "s_in": {"class": "linear", "activation": "tanh", "from": ["prev:c", "prev:orth_embed"], "n_out": 5},
      "s": {"class": "rnn_cell", "unit": "LSTMBlock", "from": ["s_in"], "n_out": 5},
      "c_in": {"class": "copy", "from": ["s"]},
      "c": {"class": "dot_attention", "from": ["c_in"], "base": "base:encoder", "base_ctx": "base:encoder"},
      "att": {"class": "linear", "activation": "tanh", "from": ["c", "s"], "n_out": 6},
      "output_prob": {"class": "softmax", "from": ["att"], "target": "classes", "loss": "ce"}
    }, "target": "classes", "max_seq_len": 75},
  }

  from GeneratingDataset import DummyDataset
  seq_len = 5
  n_data_dim = 2
  n_classes_dim = 3
  train_data = DummyDataset(input_dim=n_data_dim, output_dim=n_classes_dim, num_seqs=4, seq_len=seq_len)
  train_data.init_seq_order(epoch=1)
  cv_data = DummyDataset(input_dim=n_data_dim, output_dim=n_classes_dim, num_seqs=2, seq_len=seq_len)
  cv_data.init_seq_order(epoch=1)

  config = Config()
  config.update({
    "model": "/tmp/model",
    "num_outputs": n_classes_dim,
    "num_inputs": n_data_dim,
    "network": network,
    "start_epoch": 1,
    "num_epochs": 2,
    "batch_size": 10,
    "nadam": True,
    "learning_rate": 0.01,
  })
  engine = Engine(config=config)
  engine.init_train_from_config(config=config, train_data=train_data, dev_data=cv_data, eval_data=None)
  engine.train()


def test_deterministic_train():
  """
  Training should be deterministic, i.e. running it twice should result in exactly the same result.
  """
  network = {
    "hidden": {"class": "linear", "activation": "tanh", "n_out": 5},
    "output": {"class": "softmax", "from": ["hidden"], "target": "classes", "loss": "ce"},
  }
  n_data_dim = 2
  n_classes_dim = 3
  config = Config()
  config.update({
    "model": "/tmp/model",
    "num_outputs": n_classes_dim,
    "num_inputs": n_data_dim,
    "network": network,
    "start_epoch": 1,
    "num_epochs": 2,
    "batch_size": 10,
    "nadam": True,
    "learning_rate": 0.01,
  })

  from GeneratingDataset import DummyDataset
  seq_len = 5
  train_data = DummyDataset(input_dim=n_data_dim, output_dim=n_classes_dim, num_seqs=4, seq_len=seq_len)
  cv_data = DummyDataset(input_dim=n_data_dim, output_dim=n_classes_dim, num_seqs=2, seq_len=seq_len)

  score_results = {}  # run_idx -> epoch (1, 2) -> error_key ('dev_score', ...) -> score
  fwd_results = {}  # run_idx -> numpy array

  for run_idx in range(3):
    print("Run %i:" % run_idx)
    # Will always reinit the TF session and all random generators,
    # thus it should be deterministic.
    engine = Engine(config=config)
    engine.init_train_from_config(config=config, train_data=train_data, dev_data=cv_data, eval_data=None)
    engine.train()

    print("Run %i: Train results:" % run_idx)
    pprint(engine.learning_rate_control.epochData)
    score_results[run_idx] = {ep: d.error for (ep, d) in engine.learning_rate_control.epochData.items()}

    print("Run %i: Forward cv seq 0:" % run_idx)
    cv_data.init_seq_order(epoch=1)
    out = engine.forward_single(cv_data, 0)
    assert isinstance(out, numpy.ndarray)
    assert out.shape == (seq_len, n_classes_dim)
    print(out)
    fwd_results[run_idx] = out

    if run_idx > 0:
      for ep, error_dict in sorted(score_results[run_idx].items()):
        for error_key, error_value in sorted(error_dict.items()):
          prev_error_value = score_results[run_idx - 1][ep][error_key]
          print("Epoch %i, error key %r, current value %f vs prev value %f, equal?" % (
            ep, error_key, error_value, prev_error_value))
          numpy.testing.assert_almost_equal(error_value, prev_error_value)
      print("Output equal to previous?")
      prev_out = fwd_results[run_idx - 1]
      numpy.testing.assert_almost_equal(out, prev_out)


def test_rec_subnet_auto_optimize():
  """
  rec subnet can automatically move out layers from the loop.
  It should result in an equivalent model.
  Thus, training should be equivalent.
  Also, training the one model, and then importing it in the original model, should work.
  """
  # TODO based on test_rec_subnet_train_t3d_simple + test_deterministic_train ...


if __name__ == "__main__":
  try:
    better_exchook.install()
    if len(sys.argv) <= 1:
      for k, v in sorted(globals().items()):
        if k.startswith("test_"):
          print("-" * 40)
          print("Executing: %s" % k)
          v()
          print("-" * 40)
    else:
      assert len(sys.argv) >= 2
      for arg in sys.argv[1:]:
        print("Executing: %s" % arg)
        if arg in globals():
          globals()[arg]()  # assume function and execute
        else:
          eval(arg)  # assume Python code and execute
  finally:
    session.close()
    del session
    tf.reset_default_graph()
    import threading
    if len(list(threading.enumerate())) > 1:
      print("Warning, more than one thread at exit:")
      better_exchook.dump_all_thread_tracebacks()
