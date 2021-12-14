import logging
import pandas as pd
from threading import Thread, Event
from time import sleep
from vowpalwabbit import pyvw
from dateutil import parser

from backend.camunda.client import CamundaClient
from backend.contextual_bandit.contextual_bandit import RlEnv

logging.basicConfig(level=logging.DEBUG,
                    format='(%(threadName)-9s) %(message)s', )


class RouterManager:
    process_variant_keys = ['../resources/bpmn/helicopter_license/helicopter_vA.bpmn',
                            '../resources/bpmn/helicopter_license/helicopter_vB.bpmn']

    # Configure
    BATCH_SIZE = 200
    NUMBER_OF_VARIANTS = 2

    # format: {'A': float, 'B': float} (in seconds)
    # TODO Store in db and train on historical data
    mean_duration_results = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = CamundaClient('http://localhost:8080/engine-rest')

    def set_events(self, event_rl, event_manager):
        self.event_rl = event_rl
        self.event_manager = event_manager

    def set_RLEnv(self, rl_env):
        self.rl_env = rl_env

    def start_simulation(self):
        self.simulate_batch()
        logging.debug('BATCH SIMULATED.')
        self.event_rl.set()
        self.event_manager.clear()

        logging.debug(f'router is waiting for action')
        self.event_manager.wait(1)
        logging.debug(f'router stopped waiting for action')

        logging.debug(f'Doing some clean up.')

    def calculate_mean_variant_duration(self, data):
        # TODO: ensure order of processes is actually first A then B?
        mean_durations = []
        for process_history in data:
            instances = process_history.get('associated_instances')
            durations = []
            for instance in instances:
                start = parser.parse(instance.get('startTime'))
                end = parser.parse(instance.get('endTime'))
                duration = (end - start).total_seconds()
                durations.append(duration)
            mean_duration = sum(durations) / len(durations)
            mean_durations.append(mean_duration)

        # TODO: Prepare for more than 2 variants
        self.mean_duration_results['A'] = mean_durations[0]
        self.mean_duration_results['B'] = mean_durations[1]

    def simulate_batch(self):
        # Deploy process variants
        process_ids = self.client.deploy_processes(self.process_variant_keys)

        # Start instances
        for elem in process_ids:
            self.client.start_instances(elem, int(self.BATCH_SIZE / self.NUMBER_OF_VARIANTS))
        logging.debug('Wait for termination')
        # Wait 2 min to let the instances terminate. Hacky but check not implemented yet.
        sleep(120)

        # Get the data from the Camunda engine
        data = self.client.retrieve_data()
        # Calculate the mean reward for each variant
        self.calculate_mean_variant_duration(data)

        # Update local variable according to the simulation results
        self.rl_env.update_mean_durations(self.mean_duration_results)

        # Clean engine after retrieving the duration
        self.client.clean_process_data()


def main():
    counter = 2
    NUM_ITERATIONS = 20

    # Router
    router = RouterManager()
    # Init rl_env
    rl_env = RlEnv()

    def thread_rl():
        # Instantiate learner in VW
        vw = pyvw.vw("--cb_explore_adf -q UA --quiet --epsilon 0.2")
        #vw = pyvw.vw("--cb 2 --epsilon 0.2")

        num_iterations = 20
        acc_reward = []
        reward_sum = 0.0

        for i in range(NUM_ITERATIONS):
            reward = rl_env.init_step(vw)
            reward_sum += reward
            acc_reward.append((-1 * reward_sum / (i+1)))
            print(f'Reward Sum: {reward_sum}, Iteration: {i}')

        print(acc_reward)
        df = pd.DataFrame(acc_reward, columns=['Acc_Reward'])
        df.to_csv(f'../rl_agent/results/rewards_{counter}.csv')
        print(rl_env.actions_list)

    # Init multithreading events
    event_rl = Event()
    event_manager = Event()

    # Set events according to both env
    router.set_RLEnv(rl_env)
    rl_env.set_manager(router)
    router.set_events(event_rl, event_manager)
    rl_env.set_events(event_rl, event_manager)

    # Init RL thread
    rl_thread = Thread(name='RL Thread', target=thread_rl, args=())

    # Starting thread
    rl_thread.start()

    logging.debug('Thread started.')
    #router.client.clean_process_data()

    for n in range(NUM_ITERATIONS):
        router.start_simulation()


    while True:
        sleep(0.5)


if __name__ == "__main__":
    main()