import os

import tensorflow as tf

from audio.io import save_wav
from tacotron.input.helpers import py_pre_process_sentences, py_post_process_spectrograms
from tacotron.model import Tacotron, Mode
from tacotron.params.dataset import dataset_params
from tacotron.params.inference import inference_params
from tacotron.params.model import model_params

# Hack to force tensorflow to run on the CPU.
# os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
# os.environ["CUDA_VISIBLE_DEVICES"] = "0,1"

tf.logging.set_verbosity(tf.logging.INFO)


def inference(model, sentences):
    """
    Arguments:
        model (Tacotron):
            The Tacotron model instance to use for inference.

        sentences (:obj:`list` of :obj:`np.ndarray`):
            The padded sentences in id representation to feed to the network.

    Returns:
        spectrograms (:obj:`list` of :obj:`np.ndarray`):
            The generated linear scale magnitude spectrograms.
    """
    # Checkpoint folder to load the inference checkpoint from.
    checkpoint_load_dir = os.path.join(
        inference_params.checkpoint_dir,
        inference_params.checkpoint_load_run
    )

    if inference_params.checkpoint_file is None:
        # Get the path to the latest checkpoint file.
        checkpoint_file = tf.train.latest_checkpoint(checkpoint_load_dir)
    else:
        checkpoint_file = inference_params.checkpoint_file

    saver = tf.train.Saver()

    # Checkpoint folder to save the evaluation summaries into.
    checkpoint_save_dir = os.path.join(
        inference_params.checkpoint_dir,
        inference_params.checkpoint_save_run
    )

    # Prepare the summary writer.
    summary_writer = tf.summary.FileWriter(checkpoint_save_dir, tf.get_default_graph())
    summary_op = model.summary(mode=tf.estimator.ModeKeys.PREDICT)

    # Create the inference session.
    session = start_session()

    print('Restoring model...')
    saver.restore(session, checkpoint_file)
    print('Restoring finished')

    # Infer data.
    summary, spectrograms = session.run(
        # TODO: implement automatic stopping after a certain amount of silence was generated.
        # Then we could set max_iterations much higher and only use it as a worst case fallback
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

    session.close()

    return spectrograms


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


def main(_):
    # Before we start doing anything we check if the required target folder actually exists.
    if not os.path.isdir(inference_params.synthesis_dir):
        raise NotADirectoryError('The specified synthesis target folder does not exist.')

    # Create a dataset loader.
    dataset = dataset_params.dataset_loader(dataset_folder=dataset_params.dataset_folder,
                                            char_dict=dataset_params.vocabulary_dict,
                                            fill_dict=False)

    raw_sentences = []
    with open(inference_params.synthesis_file, 'r') as f_sent:
        for line in f_sent:
            sent = line.replace('\n', '')
            raw_sentences.append(sent)

    print("{} sentences were loaded for inference.".format(len(raw_sentences)))

    sentences = py_pre_process_sentences(raw_sentences, dataset)

    # Create a batch with only one entry.
    # sentence = np.array([sentences[0]], dtype=np.int32)

    # Create batched placeholders for inference.
    placeholders = Tacotron.model_placeholders()

    # Create the Tacotron model.
    tacotron_model = Tacotron(inputs=placeholders, mode=Mode.PREDICT)

    # generate linear scale magnitude spectrograms.
    specs = inference(tacotron_model, sentences)

    wavs = py_post_process_spectrograms(specs)

    # Write all generated waveforms to disk.
    for i, (sentence, wav) in enumerate(zip(raw_sentences, wavs)):
        # Append ".wav" to the sentence line number to get the filename.
        file_name = '{}.wav'.format(i + 1)

        # Generate the full path under which to save the wav.
        save_path = os.path.join(inference_params.synthesis_dir, file_name)

        # Write the wav to disk.
        save_wav(save_path, wav, model_params.sampling_rate, True)
        print('Saved: "{}"'.format(save_path))


if __name__ == '__main__':
    tf.logging.set_verbosity(tf.logging.INFO)
    tf.app.run()
