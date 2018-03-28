import tensorflow as tf

from tacotron.layers import cbhg


# TODO: Clean up document and comments.

class Tacotron:
    def __init__(self, hparams, inputs):
        self.hparams = hparams

        # Create placeholders for the input data.
        self.inp_mel_spec, self.inp_linear_spec, self.seq_lengths = inputs
        self.pred_linear_spec = None
        self.loss_op = None

        # Construct the network.
        self.model()

    def get_inputs_placeholders(self):
        # inp_mel_spec: shape=(N, T//r, n_mels*r)
        # inp_linear_spec: shape=(N, T//r, (1 + n_fft // 2)*r)
        return self.inp_mel_spec, self.inp_linear_spec

    def post_process(self, inputs):
        with tf.variable_scope('post_process'):
            # network.shape => (B, T//r, (1 + n_fft // 2)*r)

            # TODO: There is actually no point in applying the reduction factor during post-proc.
            #       - My measurements suggest that there is no benefit.
            #       - The Tacotron paper does not explicitly state that r was applied here.

            network = cbhg(inputs=inputs,
                           n_banks=self.hparams.post.n_banks,
                           n_filters=self.hparams.post.n_filters,
                           n_highway_layers=self.hparams.post.n_highway_layers,
                           n_highway_units=self.hparams.post.n_highway_units *
                                           self.hparams.reduction,
                           n_gru_units=self.hparams.n_gru_units,
                           training=True)

        self.pred_linear_spec = network
        return self.pred_linear_spec

    def model(self):
        # Input shape=(B, T, E)

        self.post_process(self.inp_mel_spec)

        # tf.losses.absolute_difference could be used either (in case reduction=Reduction.MEAN is used).
        self.loss_op = tf.reduce_mean(tf.abs(self.inp_linear_spec - self.pred_linear_spec))

    def get_loss_op(self):
        return self.loss_op

    def summary(self):
        tf.summary.scalar('loss', self.loss_op)

        # with tf.name_scope('reduced_inputs'):
        #     tf.summary.image('mel_spec', tf.expand_dims(self.inp_mel_spec, -1), max_outputs=1)
        #     tf.summary.image('linear_spec', tf.expand_dims(self.inp_linear_spec, -1), max_outputs=1)

        with tf.name_scope('normalized_inputs'):
            # tf.summary.image('mel_spec',
            #                  tf.expand_dims(
            #                      tf.reshape(self.inp_mel_spec[0],
            #                                 (1, -1, self.hparams.n_mels)), -1), max_outputs=1)

            tf.summary.image('linear_spec',
                             tf.expand_dims(
                                 tf.reshape(self.inp_linear_spec[0],
                                            (1, -1, (1 + self.hparams.n_fft // 2))), -1),
                             max_outputs=1)

        # with tf.name_scope('reduced_outputs'):
        #     # tf.summary.image('inp_linear_spec', tf.expand_dims(self.inp_linear_spec, -1), max_outputs=1)
        #     tf.summary.image('linear_spec', tf.expand_dims(self.pred_linear_spec, -1), max_outputs=1)

        with tf.name_scope('normalized_outputs'):
            tf.summary.image('linear_spec',
                             tf.expand_dims(
                                 tf.reshape(self.pred_linear_spec[0],
                                            (1, -1, (1 + self.hparams.n_fft // 2))), -1),
                             max_outputs=1)

        return tf.summary.merge_all()

    def load(self, checkpoint_dir):
        raise NotImplementedError()
