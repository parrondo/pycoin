import gym
import tensorflow as tf
import scipy.signal
from threading import Thread
from stockgym.a3c import A3CNetwork
import numpy as np


# Copies one set of variables to another.
# Used to set worker network parameters to those of global network.
def update_target_graph(from_scope, to_scope):
    from_vars = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, from_scope)
    to_vars = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, to_scope)

    op_holder = []
    for from_var, to_var in zip(from_vars, to_vars):
        op_holder.append(to_var.assign(from_var))
    return op_holder


def discount(x, gamma):
    return scipy.signal.lfilter([1], [1, -gamma], x[::-1], axis=0)[::-1]


class Agent(Thread):
    def __init__(self, trainer):
        super(Agent, self).__init__()
        state_dim = 9
        state_size = 111 * state_dim
        self.env = gym.make('StockGym-v0')
        self.local_AC = A3CNetwork(state_size, len(self.env.ratios), self.name, trainer)
        self.update_local_ops = update_target_graph('global', self.name)

        self.possible_actions = list(range(110 * state_dim))

        self.observations = []
        self.actions = []
        self.rewards = []
        self.values = []

    def step_env(self):
        pass

    def train(self, sess, gamma):
        n = len(self.observations)
        observations = np.array(self.observations)
        actions = np.array(self.actions)
        rewards = np.array(self.rewards)
        values = np.array(self.values)

        discounted_rewards = discount(rewards, gamma)[:-1]
        advantages = rewards + gamma * values[1:] - values[:-1]
        advantages = discount(advantages, gamma)

        run_list = [self.local_AC.value_loss, self.local_AC.policy_loss,
                    self.local_AC.entropy, self.local_AC.grad_norms,
                    self.local_AC.var_norms, self.local_AC.apply_grads]

        feed_dict = {self.local_AC.target_v: discounted_rewards,
                     self.local_AC.inputs: np.vstack(observations),
                     self.local_AC.actions: actions,
                     self.local_AC.advantages: advantages}

        value_loss, policy_loss, entropy, grads, var_norms, _ = sess.run(run_list, feed_dict=feed_dict)
        return value_loss / n, policy_loss / n, entropy / n, grads, var_norms