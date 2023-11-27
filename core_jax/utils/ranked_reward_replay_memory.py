
from functools import partial
import jax
import jax.numpy as jnp
from flax import struct
from core_jax.utils.replay_memory import EndRewardReplayBuffer, EndRewardReplayBufferState, init as super_init


@struct.dataclass
class RankedRewardReplayBufferState(EndRewardReplayBufferState):
    next_index: jnp.ndarray # next index to write experience to
    next_reward_index: jnp.ndarray # next index to write reward to
    next_raw_reward_index: jnp.ndarray # next index to write raw reward to
    buffer: struct.PyTreeNode # buffer of experiences
    reward_buffer: jnp.ndarray # buffer of ranked rewards
    raw_reward_buffer: jnp.ndarray # buffer of raw rewards
    needs_reward: jnp.ndarray # does experience need reward
    populated: jnp.ndarray # is experience populated
    key: jax.random.PRNGKey

class RankedRewardReplayBuffer(EndRewardReplayBuffer):
    def __init__(self,
        batch_size: int,
        max_len_per_batch: int,
        sample_batch_size: int,
        episode_reward_memory_len_per_batch: int,
        quantile: float = 0.75,
    ):
        super().__init__(batch_size, max_len_per_batch, sample_batch_size)
        self.quantile = quantile
        self.episode_reward_memory_len_per_batch = episode_reward_memory_len_per_batch

    def init(self, template_experience: struct.PyTreeNode) -> RankedRewardReplayBufferState:
        return init(template_experience, self.batch_size, self.max_len_per_batch, self.episode_reward_memory_len_per_batch)

    def assign_rewards(self, state: RankedRewardReplayBufferState, rewards: jnp.ndarray, select_batch: jnp.ndarray) -> RankedRewardReplayBufferState:
        return assign_rewards(state, rewards, select_batch.astype(jnp.bool_), self.max_len_per_batch, self.quantile, self.episode_reward_memory_len_per_batch)



@partial(jax.jit, static_argnums=(1,2,3))
def init(
    template_experience: struct.PyTreeNode,
    batch_size: int,
    max_len_per_batch: int,
    episode_reward_memory_len_per_batch: int,
) -> RankedRewardReplayBufferState:
    buffer_state = super_init(template_experience, batch_size, max_len_per_batch)
    return RankedRewardReplayBufferState(
        **buffer_state.__dict__, 
        raw_reward_buffer=jnp.zeros((batch_size, episode_reward_memory_len_per_batch, 1)),
        next_raw_reward_index=jnp.zeros((batch_size,), dtype=jnp.int32)
    )
    

# @partial(jax.jit, static_argnums=(3,4,5))
def assign_rewards(
    buffer_state: RankedRewardReplayBufferState,
    rewards: jnp.ndarray,
    select_batch: jnp.ndarray,
    max_len_per_batch: int,
    quantile: float,
    episode_reward_memory_len_per_batch: int,
) -> RankedRewardReplayBufferState:
    rand_key, new_key = jax.random.split(buffer_state.key)
    rand_bools = jax.random.bernoulli(rand_key, 0.5, rewards.shape)

    quantile_value = jnp.quantile(buffer_state.raw_reward_buffer, quantile, axis=1).mean()


    def rank_rewards(reward, boolean):
        return jnp.where(
            reward < quantile_value, 
            -1,
            jnp.where(
                reward > quantile_value,
                1,
                jnp.where(
                    boolean,
                    1,
                    -1
                )
            )
        )
    
    ranked_rewards = rank_rewards(rewards, rand_bools)

    ranked_rewards = jax.vmap(jnp.roll, in_axes=(0, 0))(ranked_rewards, buffer_state.next_reward_index)
    ranked_rewards = jnp.tile(ranked_rewards, (1, max_len_per_batch // ranked_rewards.shape[-1]))
    
    
    
    return buffer_state.replace(
        key=new_key,
        reward_buffer = jnp.where(
            select_batch[..., None, None] & buffer_state.needs_reward,
            ranked_rewards[..., None],
            buffer_state.reward_buffer
        ),
        raw_reward_buffer = buffer_state.raw_reward_buffer.at[:, buffer_state.next_raw_reward_index, 0].set(
            jnp.where(
                select_batch,
                rewards,
                buffer_state.raw_reward_buffer[:, buffer_state.next_raw_reward_index, 0]
            )    
        ),
        next_reward_index = jnp.where(
            select_batch,
            buffer_state.next_index,
            buffer_state.next_reward_index
        ),
        next_raw_reward_index = jnp.where(
            select_batch,
            (buffer_state.next_raw_reward_index + 1) % episode_reward_memory_len_per_batch,
            buffer_state.next_raw_reward_index
        ),
        needs_reward = jnp.where(
            select_batch[..., None, None],
            False,
            buffer_state.needs_reward
        )
    )