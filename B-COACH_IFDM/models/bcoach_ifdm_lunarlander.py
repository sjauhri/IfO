from utils import *
from bcoach_ifdm import BCOACH
from feedback import *
from fdm_lunarl import *
import gym

class BCOACH_lunarlander(BCOACH):
  def __init__(self, state_shape, action_shape, lr=0.001, maxEpochs=20, epochTrainIts=7000, M=200, batch_size=32):
    BCOACH.__init__(self, state_shape, action_shape, lr=lr, maxEpochs=maxEpochs, epochTrainIts=epochTrainIts, M=M, batch_size=batch_size)

    # set which game to play
    self.env = gym.make('LunarLander-v2')
    self.env.reset()
    self.env.render()  # Make the environment visible
    #pdb.set_trace()
    #print(self.env.observation_space.high)

    # Initialise Human feedback (call render before this)
    self.human_feedback = Feedback(self.env)
    # Set error constant multiplier for this environment
    # 0.01, 0.05, 0.1, 0.5, 1, 5
    self.errorConst = 0.1
    # Render time delay for this environment (in s)
    self.render_delay = 0.05
    # Choose which feedback is valid with fb dictionary
    self.feedback_dict = {
      H_NULL: 0,
      H_UP: 1,
      H_DOWN: 1,
      H_LEFT: 1,
      H_RIGHT: 1,
      DO_NOTHING: 1
    }

    self.ifdm_queries = 24 # Four discrete actions. (Easy)
  
  def build_policy_model(self):
    """buliding the policy model as two fully connected layers with leaky relu"""
    with tf.variable_scope("policy_model") as scope:
      with tf.variable_scope("input") as scope:
        policy_input = self.state
      with tf.variable_scope("model") as scope:
        policy_h1 = tf.layers.dense(policy_input, 32, kernel_initializer=weight_initializer(), bias_initializer=bias_initializer(), name="dense_1")
        policy_h1 = tf.nn.leaky_relu(policy_h1, 0.001, name="LeakyRelu_1")
        policy_h2 = tf.layers.dense(policy_h1, 32, kernel_initializer=weight_initializer(), bias_initializer=bias_initializer(), name="dense_2")
        policy_h2 = tf.nn.leaky_relu(policy_h2, 0.001, name="LeakyRelu_2")

      with tf.variable_scope("output") as scope:
        policy_pred_action = tf.layers.dense(policy_h2, self.action_dim, kernel_initializer=weight_initializer(), bias_initializer=bias_initializer(), name="dense")
        self.tmp_policy_pred_action = policy_pred_action
        self.policy_pred_action = tf.one_hot(tf.argmax(policy_pred_action, axis=1), self.action_dim, name="one_hot")

      with tf.variable_scope("loss") as scope:
        self.policy_loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(labels=self.action, logits=policy_pred_action))
      with tf.variable_scope("train_step") as scope:
        self.policy_train_step = tf.train.AdamOptimizer(self.lr).minimize(self.policy_loss)

  def build_idm_model(self):
    """building the inverse dynamic model as two fully connnected layers with leaky relu"""
    with tf.variable_scope("inverse_dynamic_model") as scope:
      with tf.variable_scope("input") as scope:
        idm_input = tf.concat([self.state, self.nstate], 1)
      with tf.variable_scope("model") as scope:
        idm_h1 = tf.layers.dense(idm_input, 32, kernel_initializer=weight_initializer(), bias_initializer=bias_initializer(), name="dense_1")
        idm_h1 = tf.nn.leaky_relu(idm_h1, 0.2, name="LeakyRelu_1")
        idm_h2 = tf.layers.dense(idm_h1, 32, kernel_initializer=weight_initializer(), bias_initializer=bias_initializer(), name="dense_2")
        idm_h2 = tf.nn.leaky_relu(idm_h2, 0.2, name="LeakyRelu_2")

      with tf.variable_scope("output") as scope:
        idm_pred_action = tf.layers.dense(idm_h2, self.action_dim, kernel_initializer=weight_initializer(), bias_initializer=bias_initializer(), name="dense")
        self.idm_pred_action = tf.one_hot(tf.argmax(idm_pred_action, axis=1), self.action_dim, name="one_hot")

      with tf.variable_scope("loss") as scope:
        self.idm_loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(labels=self.action, logits=idm_pred_action))
      with tf.variable_scope("train_step") as scope:
        self.idm_train_step = tf.train.AdamOptimizer(self.lr).minimize(self.idm_loss)

  def pre_demonstration(self):
    """uniform sample action to generate (s_t, s_t+1) and action pairs"""
    terminal = True
    States = []
    Nstates = []
    Actions = []

    for i in range(int(round(self.M / self.alpha))):
      if terminal:
        state = self.env.reset()

      prev_s = state
      state = np.reshape(state, [-1, self.state_dim])

      A = np.random.randint(self.action_dim)
      a = np.zeros([self.action_dim])
      a[A] = 1

      state, _, terminal, _ = self.env.step(A)

      States.append(prev_s)
      Nstates.append(state)
      Actions.append(a)

      if i and (i+1) % 1000 == 0:
        print("Collecting idm training data ", i+1)
        self.log_writer.write("Collecting idm training data " + str(i+1) + "\n")

    return States, Nstates, Actions

  def get_state_corrected(self, h_fb, state):
    """get corrected state label for this environment using feedback"""
    state_corrected = np.copy(state)

    if (h_fb == H_LEFT): # Angular velocity
      state_corrected = state_corrected[5] + self.errorConst      
    elif (h_fb == H_RIGHT):
      state_corrected = state_corrected[5] - self.errorConst      
    elif (h_fb == H_UP): # Vertical velocity
      state_corrected = state_corrected[3] + self.errorConst
    elif (h_fb == H_DOWN):
      state_corrected = state_corrected[3] - self.errorConst/5
    return state_corrected

  def get_action(self, h_fb, state, state_corrected):
    """get action to achieve close next state close to state_corrected"""
    # Discrete Actions
    min_action = np.random.randint(self.action_dim)
    min_cost = np.Inf
    
    if (h_fb == DO_NOTHING):
      min_action = 0 # Do Nothing action
    else:      
      for _ in range(1, self.ifdm_queries+1):
        # Choose random action
        # Discrete actions
        curr_action = np.random.randint(self.action_dim)

        # Query ifdm to get next state
        nstate = fdm(state, curr_action)

        # Check cost
        if ((h_fb == H_LEFT) or (h_fb == H_RIGHT)): # Angular velocity
          cost = abs(state_corrected - nstate[5])
        else:                                       # Vertical velocity
          cost = abs(state_corrected - nstate[3])
        
        # Check for min_cost
        if(cost < min_cost):
          min_cost = cost
          min_action = curr_action

    return min_action

  def coach(self):
    """COACH algorithm incorporating human feedback"""
    terminal = False
    state = self.env.reset()
    state = np.reshape(state, [-1, self.state_dim])
    t_counter = 0
    h_counter = 0

    # Iterate over the episode
    while((not terminal) and (not self.human_feedback.ask_for_done()) ):        
      self.env.render()  # Make the environment visible
      time.sleep(self.render_delay)    # Add delay to rendering if necessary
      
      # Store previous_state
      prev_s = state

      # Get feedback signal
      h_fb = self.human_feedback.get_h()
      # Debug
      # h_fb = 3

      # Update policy
      if (self.feedback_dict.get(h_fb) != 0):  # if feedback is not zero i.e. is valid
        print("Feedback", self.feedback_dict.get(h_fb))
        h_counter += 1 # Feedback counter

        # Get new state transition label using feedback
        state_corrected = self.get_state_corrected(h_fb, state[0])        

        # Get action from ifdm
        A = self.get_action(h_fb, state[0], state_corrected)
        # Discrete actions: a = A in one hot with extra braces
        a = np.zeros(self.action_dim)
        a[A] = 1
        print("Computed_IFDM action: ", a)
        # Debug incorrect action
        # if not args.cont_actions:
        #   if ((self.feedback_dict.get(h_fb) == -1 and a[0][1] == 1) or (self.feedback_dict.get(h_fb) == 1 and a[0][0] == 1)):
        #     print("MISLABEL!")
        # else:
        #   if ((self.feedback_dict.get(h_fb) == -1 and a[0][1] > 0.5) or (self.feedback_dict.get(h_fb) == 1 and a[0][1] < -0.5)):
        #     print("MISLABEL!")

        # Update policy (immediate)
        a = np.reshape(a, [-1, self.action_dim])
        self.update_policy_feedback_immediate(state, a)

        # Add state transition pair to demo buffer
        self.DemoBuff.append((state[0], a[0]))
        # If Demo buffer full, remove oldest entry
        if (len(self.DemoBuff) > self.maxDemoBuffSize):
            self.DemoBuff.pop(0)

        # Train with batch from Demo buffer (if enough entries exist)
        self.update_policy_feedback()

        # Act using action based on h_feedback
        A = np.reshape(a, [-1])
        # Discrete actions
        A = np.argmax(A)        
        state, _, terminal, _ = self.env.step(A)
        state = np.reshape(state, [-1, self.state_dim])
        # TODO: Add to ExpBuff
      else:
        # Use current policy
        # Map action from state        
        A = np.reshape(self.eval_policy(state), [-1])
        # Discrete actions
        A = np.argmax(A)

        # Act
        state, _, terminal, _ = self.env.step(A)
        state = np.reshape(state, [-1, self.state_dim])
        # TODO: Add to ExpBuff

        # Train every k time steps
      if t_counter % self.coach_training_rate == 0:
        self.update_policy_feedback()

      t_counter += 1 # Time counter

  def post_demonstration(self, M):
    """using policy to generate (s_t, s_t+1) and action pairs"""
    terminal = True
    States = []
    Nstates = []
    Actions = []

    for i in range(M):
      if terminal:
        state = self.env.reset()

      prev_s = state
      state = np.reshape(state, [-1,self.state_dim])

      a = np.reshape(self.eval_policy(state), [-1])
      A = np.argmax(a)
      state, _, terminal, _ = self.env.step(A)

      States.append(prev_s)
      Nstates.append(state)
      Actions.append(a)

    return States, Nstates, Actions

  def eval_rwd_policy(self):
    """getting the reward by current policy model"""
    terminal = False
    total_reward = 0
    state = self.env.reset()

    while not terminal:
      state = np.reshape(state, [-1,self.state_dim])
      a = np.reshape(self.eval_policy(state), [-1])
      A = np.argmax(a)
      state, reward, terminal, _ = self.env.step(A)
      total_reward += reward
      if args.render:
        self.env.render()
        time.sleep(self.render_delay)

    return total_reward
    
if __name__ == "__main__":
  bcoach = BCOACH_lunarlander(8, 4, lr=args.lr, maxEpochs=args.maxEpochs)
  bcoach.run()
