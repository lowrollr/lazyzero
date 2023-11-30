


from typing import Tuple
import jax
import jax.numpy as jnp
from core_jax.envs.env import Env, EnvState
import jumanji
from jumanji.env import Environment as JEnv
from flax import struct

from core_jax.utils.action_utils import unflatten_action

class JumanjiEnv(Env):
    def __init__(self, jumanji_env: JEnv):
        super().__init__(
            env = jumanji_env,
        )
        self._env: JEnv

        dims = self.get_action_shape()
        self.unflatten = unflatten_action 
        if type(dims) == int:
            dims = (dims,)
            self.unflatten = lambda x, _: x
    
    def get_action_shape(self) -> Tuple[int]:
        return self._env.action_spec().num_values
    
    def get_observation_shape(self) -> Tuple[int]:
        return self._env.observation_spec().shape
    
    def num_players(self) -> int:
        return 1
    
    def step(self, state: EnvState, action: jnp.ndarray) -> Tuple[EnvState, jnp.ndarray]:
        # returns state, observation, reward, terminated
        env_state, timestep = self._env.step(state._state, self.unflatten(action, self.action_space_dims))
        return state.replace(
            legal_action_mask=timestep.observation.action_mask,
            reward=timestep.reward.reshape(-1),
            _state=env_state,
            _observation=timestep.observation,
        ), timestep.last()
    
    def reset(self, key: jax.random.PRNGKey) -> Tuple[EnvState, jnp.ndarray]:
        cls_key, base_key = jax.random.split(key)
        env_state, timestep = self._env.reset(base_key)
        return EnvState(
            key=cls_key,
            legal_action_mask=timestep.observation.action_mask,
            reward=timestep.reward.reshape(-1),
            cur_player_id = jnp.array([0]),
            _state=env_state,
            _observation=timestep.observation,
        ), timestep.last()


def make_jumanji_env(env_name, *args, **kwargs) -> JumanjiEnv:
    jenv = jumanji.make(env_name, *args, **kwargs)
    return JumanjiEnv(jenv)