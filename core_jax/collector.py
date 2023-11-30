
from functools import partial
import jax
import jax.numpy as jnp

from flax import struct
from dataclasses import dataclass

from core_jax.envs.env import EnvState, Env
from core_jax.evaluators.evaluator import Evaluator, EvaluatorState
from core_jax.utils.replay_memory import EndRewardReplayBuffer, EndRewardReplayBufferState


@dataclass
class CollectorConfig:
    pass

@struct.dataclass
class CollectorState:
    evaluator_state: EvaluatorState
    env_state: EnvState
    buff_state: EndRewardReplayBufferState

@struct.dataclass
class BaseExperience(struct.PyTreeNode):
    observation: struct.PyTreeNode
    policy: jnp.ndarray
    policy_mask: jnp.ndarray


class Collector:
    def __init__(self, 
        config: CollectorConfig,
        env: Env,
        evaluator: Evaluator,
        buff: EndRewardReplayBuffer 
    ): 
        self.config = config
        self.env = env
        self.evaluator = evaluator
        self.buff = buff

    def init(self, 
        env_state: EnvState, 
        eval_state: EvaluatorState
    ) -> CollectorState:
        buff_state = self.buff.init(
            jax.tree_map(
                lambda x: jnp.zeros(x.shape[1:], x.dtype),
                BaseExperience(
                    observation=env_state._observation,
                    policy=jax.vmap(self.evaluator.get_policy)(eval_state),
                    policy_mask=env_state.legal_action_mask
                )
            )
            
        )

        return CollectorState(
            evaluator_state=eval_state,
            env_state=env_state,
            buff_state=buff_state
        )

    def collect_step(self,
        state: CollectorState,
    ) -> CollectorState:
        env_state, eval_state, buff_state = state.env_state, state.evaluator_state, state.buff_state
        observation = env_state._observation
        eval_state = jax.vmap(self.evaluator.evaluate)(eval_state, env_state)
        eval_state, action = jax.vmap(self.evaluator.choose_action)(eval_state, env_state)
        env_state, terminated = jax.vmap(self.env.step)(env_state, action)

        buff_state = self.buff.add_experience(
            buff_state,
            BaseExperience(
                observation=observation,
                policy=jax.vmap(self.evaluator.get_policy)(eval_state),
                policy_mask=env_state.legal_action_mask
            )
        )

        eval_state = jax.vmap(self.evaluator.step_evaluator)(eval_state, action, terminated)
        env_state, terminated = jax.vmap(self.env.reset_if_terminated)(env_state, terminated)

        return state.replace(
            env_state=env_state,
            evaluator_state=eval_state,
            buff_state=buff_state
        )