# Single-Speaker End-to-End Neural Text-to-Speech Synthesis

<!-- [![Build status](https://circleci.com/gh/)](https://circleci.com/gh/) -->
[![License](https://img.shields.io/github/license/mashape/apistatus.svg)](https://github.com/yweweler/single-speaker-tts/blob/master/LICENSE)

This is a single-speaker neural text-to-speech (TTS) system capable of training in a end-to-end fashion.
It is inspired by the [Tacotron](https://arxiv.org/abs/1703.10135v2) architecture and able to train
 based on unaligned text-audio pairs.
The implementation is based on [Tensorflow](https://tensorflow.org/).

![Header](readme/images/header.png)


## Contents

- [Examples](#toc-examples)
- [Prerequisites](#toc-prerequisites)
- [Installation](#toc-installation)
- [Dataset Preparation](#toc-preparation)
  1. [Signal Statistics](#toc-preparation-signal-stats)
  2. [Feature Pre-Calculation](#toc-preparation-feature-pre-calc)
- [Training](#toc-training)
- [Evaluation](#toc-evaluation)
- [Inference](#toc-inference)
- [Architecture](#toc-arch)
  1. [Attention](#toc-arch-attention)
  2. [Decoder](#toc-arch-cbhg)
  3. [Decoder](#toc-arch-encoder)
  4. [Decoder](#toc-arch-decoder)
  5. [Post-Processing](#toc-arch-post-processing)
- [Pre-Trained Models](#toc-models)
- [Contributing](#toc-contrib)
- [License](#toc-license)


## <a name="toc-examples">Examples</a>

* After 500k steps on the the Blizzard Challenge 2011 dataset (Nancy Corpus):
  - ![WAV17](readme/audio/nancy/17.wav)
  - ![WAV24](readme/audio/nancy/24.wav)
  - ![WAV25](readme/audio/nancy/25.wav)
  - ![WAV31](readme/audio/nancy/31.wav)
  - ![WAV36](readme/audio/nancy/36.wav)
  - ![WAV37](readme/audio/nancy/37.wav)
  - ![WAV47](readme/audio/nancy/47.wav)
  - ![WAV50](readme/audio/nancy/50.wav)


## <a name="toc-prerequisites">Prerequisites</a>

On machines where Python 3 is not the default Python runtime, you should use ``pip3`` instead of ``pip``.

```bash
# Make sure you have installed python3.
sudo apt-get install python3 python3-pip

# Make sure you have installed the python3 `virtualenv` module.
sudo pip3 install virtualenv
```


## <a name="toc-installation">Installation</a>

```bash
# Create a virtual environment using python3.
virtualenv <my-venv-name> -p python3

# Activate the virtual environment.
source <my-env-name>/bin/activate

# Clone the repository.
git clone https://github.com/yweweler/single-speaker-tts.git

# Install the requirements.
cd single-speaker-tts
pip3 install -r requirements.txt

# Set up the PYTHONPATH environment variable to include the project.
export PWD=$(pwd)
export PYTHONPATH=$PYTHONPATH:$PWD/tacotron:$PWD
```


## <a name="toc-preparation">Dataset Preparation</a>

Datasets are loaded using dataset loaders.
Currently each dataset requires a custom dataset loader to be written.
Depending on how the loader does its job the datasets can be stored in nearly any form and file-format.
If you want to use a custom dataset you have to write a custom loading helper.
However, a few custom loaders for datasets exist already.

See: [datasets/](datasets/)
```bash
datasets/
├── blizzard_nancy.py
├── cmu_slt.py
├── lj_speech.py
...
```

Please take a look at [LJSPEECH.md](LJSPEECH.md) for a full step by step tutorial on how to train
 a model on the LJ Speech v1.1 dataset.

### <a name="toc-preparation-signal-stats">Signal Statistics</a>

In order to create a model the exact character vocabulary and certain signal boundaries have to 
be calculated for normalization.
The model uses linear scale as well as Mel scale spectrograms for synthesis.
All spectrograms are scaled linearly to fit the range `(0.0, 1.0)` using global minimum and 
maximum dB values calculated on the training corpus.

First we have to configure the dataset in [tacotron/params/dataset.py](tacotron/params/dataset.py).
Enter the path to the dataset `dataset_folder` and set the `dataset_loader` variable to te 
loader required for your dataset.

Then calculate the vocabulary and the signal boundaries using:
```bash
python tacotron/dataset_statistics.py

Dataset: /my-dataset-path/LJSpeech-1.1
Loading dataset ...
Dataset vocabulary:
vocabulary_dict={
    'pad': 0,
    'eos': 1,
    'p': 2,
    'r': 3,
    'i': 4,
    'n': 5,
    't': 6,
    'g': 7,
    ' ': 8,
    'h': 9,
    'e': 10,
    'o': 11,
    'l': 12,
    'y': 13,
    's': 14,
    'w': 15,
    'c': 16,
    'a': 17,
    'd': 18,
    'f': 19,
    'm': 20,
    'x': 21,
    'b': 22,
    'v': 23,
    'u': 24,
    'k': 25,
    'j': 26,
    'z': 27,
    'q': 28,
},
vocabulary_size=29


Collecting decibel statistics for 13100 files ...
mel_mag_ref_db =  6.026512479977281
mel_mag_max_db =  -99.89414986824931
linear_ref_db =  35.65918850818663
linear_mag_max_db =  -100.0
```

Now complement `vocabulary_dict` and `vocabulary_size` in [tacotron/params/dataset.py](tacotron/params/dataset.py) and transfer the decibel boundaries (`mel_mag_ref_db`, 
`mel_mag_max_db`, `linear_ref_db`, `linear_mag_max_db`) to your loader.
Each loader derived from `DatasetHelper` has to define these variables in order to be able to 
normalize the audio files.

### <a name="toc-preparation-feature-pre-calc">Feature Pre-Calculation</a>

Instead of calculating features on demand during training or evaluation, the code also allows to 
pre-calculate features and store them on disk.

To pre-calculate features run:
```bash
python tacotron/dataset_precalc_features.py
```

The pre-computed features are stored as `.npz` files next to the actual audio files.
Note that independent from pre-calculation, features can also be cached in RAM to accelerate throughput.

If you then want to use these features during training, just set `load_preprocessed=True` in 
[tacotron/params/training.py](tacotron/params/training.py).
And in case you have enough RAM consider also setting `cache_preprocessed=True` to cache all 
features in RAM.


## <a name="toc-training">Training</a>

Configure the desired parameters for the model:

- Setup the dataset path and the loader in [tacotron/params/dataset.py](tacotron/params/model.py).
- [Calculate and set the signal statistics.](#toc-preparation-signal-stats)
- Setup the architecture parameters in [tacotron/params/architecture.py](tacotron/params/architecture.py).
- **Optional**: [Pre-calculate the features for the architecture.](#toc-preparation-feature-pre-calc)
- Setup the training parameters in [tacotron/params/training.py](tacotron/params/training.py).

Start the training process:
```bash
python tacotron/train.py
```

You can stop the training process any time by killing the training process using ``CTRL+C`` on the terminal for example.

Note that you can *resume training* at the last saved checkpoint by just starting the training process again.
The training code will then look for the most recent checkpoint in the checkpoint folder configured.
However, keep in mind that the architecture is configured to use CUDNN per default.
Keep this in mind in case you are planning to restore checkpoints later on different machine.

For a in depth step by step example with the LJ Speech dataset take a look at [LJSPEECH.md](LJSPEECH.md).


### Training Progress

Progress of model can be observed through Tensorboard.
```bash
tensorboard --logdir <path-to-your-checkpoint-folder>
```

Now open `localhost:6006` with your browser to enter Tensorboard.


## <a name="toc-evaluation">Evaluation</a>

Configure the desired evaluation parameters:

- Setup the dataset path and the loader in [tacotron/params/dataset.py](tacotron/params/model.py).
- [Calculate and set the signal statistics.](#toc-preparation-signal-stats)
- **Optional**: [Pre-calculate the features for the architecture.](#toc-preparation-feature-pre-calc)
- Setup the evaluation parameters in [tacotron/params/evaluation.py](tacotron/params/evaluation.py).

Start the evaluation process:
```bash
python tacotron/evaluate.py
```

If configured, the evaluation code will sequentially load all training checkpoints from a folder and evaluate each of them.


## <a name="toc-inference">Inference</a>

Configure the desired inference parameters:

1. Setup the inference parameters in [tacotron/params/inference.py](tacotron/params/inference.py).
2. Place a file with all the sentences to synthesize at the location configured. (A simple text 
file with one sentence per line)

Start the inference process:
```bash
python tacotron/inference.py
```

Your synthesized files (and debug outputs) are dropped into the configured folder.

### Spectrogram Power

The magnitudes of the produced linear spectrogram are raised to a power (default is `1.3`) to
reduce perceived noise.

![spectrogram_raised_to_a_power](readme/images/power.png)

This parameter is not learned by a model. It has to be determined for each dataset manually.
There is no direct rule on what value is best.
However, note that higher values tend to suppress the higher frequencies of the produced voice. This leads to a voice is muffled.
Usually a value greater `1.0` and bellow `1.6` works best (depending on the amount of noise perceived).


## <a name="toc-arch">Architecture</a>

The architecture is inspired by the [Tacotron](https://arxiv.org/abs/1703.10135v2) architecture and takes unaligned text-audio pairs as input.
Based on entered text it produces linear-scale frequency magnitude spectrograms and an alignment 
between text and audio.

The architecture is constructed from four main stages:

1. Encoder
2. Decoder
3. Post-Processing
4. Waveform synthesis

The encoder takes written sentences and generates variable length embeddings for each sentence.
The subsequent decoder decodes the variable length embedding into a Mel-spectrogram.
With each decoding iteration the decoder predicts `r` spectrogram frames at once.
The frames predicted with each iteration are concatenated to form the complete Mel-spectrogram.
To predict the spectrogram the decoder's attention mechanism selects the character embeddings (`memory`) it deems most important for decoding.
The post-processing stage upgrades the Mel-spectrogram into a linear-scale spectrogram.
It's job is to improve the spectrograms and pull up the Mel-spectrogram to linear-scale.
Finally, the Griffin-Lim algorithm is used for the synthesis stage to retrieve the final waveform.

![Overview](readme/images/architecture.png)

### <a name="toc-arch-attention">Attention</a>

Instead of the [Bahdanau](https://arxiv.org/abs/1409.0473v7) style attention mechanism Tacotron 
uses, the architecture employs [Luong](https://arxiv.org/abs/1508.04025v5) style attention.
We implemented the global as well as local attention approaches as described by Luong.
Note however, that the local attention approach is somewhat basic and experimental.

As the encoder CBHG is bidirectional the concatenated forward and backward hidden states are fed 
to the attention mechanism.

![Attention](readme/images/attention.png)

#### Alignments

The attention mechanism predicts an probability distribution over the the encoder hidden states 
with each decoder step.
Concatenating these leads to the actual alignments for the encoder and the decoder sequence.

As an example take a look at the progress of the alignment predicted after different amounts of 
training.

![Alignments](readme/images/alignments.png)

### <a name="toc-arch-cbhg">CBHG</a>

The CBHG (1-D convolution bank + highway network + bidirectional GRU) module is adopted from the Tacotron architecture.
It is used both in the encoder and the post-processing.
Take a look at the implementation for more details on how it works 
[tacotron/layers.py](tacotron/layers.py#L448).

![CBHG](readme/images/cbhg.png)

### <a name="toc-arch-encoder">Encoder</a>

First the encoder converts the characters of entered sentences into character embeddings.
Like in Tacotron, these embeddings are then further processed by a `pre-net` and a `CBHG` module.

![Encoder](readme/images/encoder.png)

### <a name="toc-arch-decoder">Decoder</a>

The decoder decodes `r` subsequent Mel-spectrogram frames with each decoding iteration.
The `r-1`'th frame is used as the input for the next iteration.
The hidden states and the first input are initialized using zero vectors.
Currently decoding is stopped after a set number of iterations, see 
[tacotron/params/model.py](tacotron/params/model.py#L108).
However, the code is generally capable of stopping if a certain condition is met during decoding.
Just take a look at [tacotron/helpers.py](tacotron/helpers.py#L134).

Most of the models trained during development used `r = 5`.
Note that using reduction factors of `8` and greater lead to an massive decrease in the attention 
alignments robustness.

![Decoder](readme/images/decoder.png)

### <a name="toc-arch-post-processing">Post-Processing</a>

The post-processing stage is supposed to remove artifacts and produce a linear scale spectrogram.
The Mel-spectrogram is first transformed into a intermediate representation by a `CBHG` module.
Note that this intermediate representation is not enforced to be a spectrogram.
Finally, a simple dense layer is used to produce the linear-scale spectrogram.

![Post-Processing](readme/images/post-processing.png)


## <a name="toc-models">Pre-Trained Models</a>

Currently I do not plan to deliver pre-trained models as their distribution might interfere with
the licenses of the datasets used.
If you are interested in pre-trained models please feel free to message me.

If you are willing to provide pre-trained checkpoints for the model on your own, feel free to open a pull-request.


## <a name="toc-contrib">Contributing</a>

All contributions are warmly welcomed. Below are a few hints to the entry points of the code and a link to the to do list.
Just open a pull request with your proposed changes.

### Entry Points
* The model architecture is implemented in [tacotron/model.py](tacotron/model.py).
* The model architecture parameters are defined in [tacotron/params/model.py](tacotron/params/model.py).
* The train code is defined [tacotron/train.py](tacotron/train.py).
* Take a look at [datasets/blizzard_nancy.py](datasets/blizzard_nancy.py) to see how a dataset loading helper has to implemented.

### Todo
See [Issues](https://github.com/yweweler/single-speaker-tts/issues)


## <a name="toc-license">License</a>

```
Copyright 2018 Yves-Noel Weweler

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```

See [LICENSE.txt](https://github.com/yweweler/single-speaker-tts/blob/master/LICENSE)
