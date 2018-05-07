import os

import numpy as np
import tensorflow as tf

from audio.conversion import inv_normalize_decibel, decibel_to_magnitude, ms_to_samples
from audio.io import save_wav
from audio.synthesis import spectrogram_to_wav
from tacotron.model import Tacotron, Mode
from tacotron.params.dataset import dataset_params
from tacotron.params.inference import inference_params
from tacotron.params.model import model_params

# Hack to force tensorflow to run on the CPU.
# os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
# os.environ["CUDA_VISIBLE_DEVICES"] = ""

tf.logging.set_verbosity(tf.logging.INFO)


def pad_sentence(_sentence, _max_len):
    pad_len = _max_len - len(_sentence)
    pad_token = dataset_params.vocabulary_dict['pad']
    _sentence = np.append(_sentence, [pad_token] * pad_len)

    return _sentence


def inference(model, sentences):
    """
    Arguments:
        model (Tacotron):
            The Tacotron model instance to use for inference.

        sentences (:obj:`list` of :obj:`np.ndarray`):
            The padded sentences in id representation to feed to the network.

    Returns:
        wavs (:obj:`list` of :obj:`np.ndarray`):
            The synthesised waveforms.
    """
    # Checkpoint folder to load the inference checkpoint from.
    checkpoint_load_dir = os.path.join(
        inference_params.checkpoint_dir,
        inference_params.checkpoint_load_run
    )

    # Get the path to the latest checkpoint file.
    checkpoint_file = tf.train.latest_checkpoint(checkpoint_load_dir)
    saver = tf.train.Saver()

    # Checkpoint folder to save the evaluation summaries into.
    checkpoint_save_dir = os.path.join(
        inference_params.checkpoint_dir,
        inference_params.checkpoint_save_run
    )

    # Prepare the summary writer.
    summary_writer = tf.summary.FileWriter(checkpoint_save_dir, tf.get_default_graph())
    summary_op = tacotron_model.summary()

    # Create the inference session.
    session = start_session()

    print('Restoring model...')
    saver.restore(session, checkpoint_file)
    print('Restoring finished')

    # Infer data.
    summary, spectrograms = session.run(
        # TODO: implement automatic stopping after a certain amount of silence was generated.
        # The we could set max_iterations much higher and only use it as a worst case fallback
        # when the network does not stop by itself.
        [
            summary_op,
            model.output_linear_spec
        ],
        feed_dict={
            model.inp_sentences: sentences
        })

    # Write the summary statistics.
    inference_summary = tf.Summary()
    inference_summary.ParseFromString(summary)
    summary_writer.add_summary(inference_summary)

    win_len = ms_to_samples(model_params.win_len, model_params.sampling_rate)
    win_hop = ms_to_samples(model_params.win_hop, model_params.sampling_rate)
    n_fft = model_params.n_fft

    # Apply Griffin-Lim to all spectrogram's to get the waveforms.
    wavs = list()
    for spectrogram in spectrograms:
        print('Reverse spectrogram normalization ...', spectrogram.shape)
        linear_mag_db = inv_normalize_decibel(spectrogram.T,
                                              dataset_params.dataset_loader.mel_mag_ref_db,
                                              dataset_params.dataset_loader.mel_mag_max_db)

        linear_mag = decibel_to_magnitude(linear_mag_db)

        print('Spectrogram inversion ...')
        wav = spectrogram_to_wav(linear_mag,
                                 win_len,
                                 win_hop,
                                 n_fft,
                                 model_params.reconstruction_iterations)

        wavs.append(wav)

    session.close()

    return wavs


def start_session():
    """
    Creates a session that can be used for training.

    Returns:
        tf.Session
    """

    session_config = tf.ConfigProto(
        gpu_options=tf.GPUOptions(
            allow_growth=True,
        )
    )

    session = tf.Session(config=session_config)

    init_op = tf.group(tf.global_variables_initializer(), tf.local_variables_initializer())
    session.run(init_op)

    return session


if __name__ == '__main__':
    # Before we start doing anything we check if the required target folder actually exists.
    if not os.path.isdir(inference_params.synthesis_dir):
        raise NotADirectoryError('The specified synthesis target folder does not exist.')

    # Create a dataset loader.
    dataset = dataset_params.dataset_loader(dataset_folder=dataset_params.dataset_folder,
                                            char_dict=dataset_params.vocabulary_dict,
                                            fill_dict=False)

    raw_sentences = [
        'A short sentence.',
        'I can\'t dance, I can\'t talk. Only thing about me is the way I walk.',
        'We are the borg, lower your shields and surrender your ships, we will add your '
        'biological and technological distinctiveness to our own.',
        'We are the borg resistance is futile.',
        'This sentence           contains many spaces.'
    ]

    # Pre-process sentence and convert it into ids.
    id_sequences, sequence_lengths = dataset.process_sentences(raw_sentences)

    # Get the first sentence.
    sentences = [np.fromstring(id_sequence, dtype=np.int32) for id_sequence in id_sequences]

    # Pad sentence to the same length in order to be able to batch them in a single tensor.
    max_length = max(sequence_lengths)
    sentences = [pad_sentence(sentence, max_length) for sentence in sentences]

    # Create a batch with only one entry.
    # sentence = np.array([sentences[0]], dtype=np.int32)

    # Create batched placeholders for inference.
    placeholders = Tacotron.model_placeholders()

    # Create the Tacotron model.
    tacotron_model = Tacotron(inputs=placeholders, mode=Mode.PREDICT)

    # Train the model.
    wavs = inference(tacotron_model, sentences)

    # Write all generated waveforms to disk.
    for sentence, wav in zip(raw_sentences, wavs):
        # Make sentence lowercase and remove all non alphabetic characters.
        sentence = ''.join(filter(str.isalnum, sentence.lower()))

        # Append ".wav" to the sentence get the filename.
        file_name = '{}.wav'.format(sentence)

        # Generate the full path under which to save the wav.
        save_path = os.path.join(inference_params.synthesis_dir, file_name)

        # Write the wav to disk.
        save_wav(save_path, wav, model_params.sampling_rate, True)
        print('Saved: "{}"'.format(save_path))