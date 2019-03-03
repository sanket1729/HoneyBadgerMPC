from honeybadgermpc.mpc import *
import logging
import asyncio
from honeybadgermpc.field import GF
from gmpy2 import num_digits
from honeybadgermpc.mixins import BeaverTriple, MixinOpName
from math import sqrt

async def comparison(context, a_share, b_share):
	"""MULTIPARTY COMPARISON - An Improved Multiparty Protocol for 
	Comparison of Secret-shared Values by Tord Ingolf Reistad (2007)
	This method `greater_than_equal` method which can compare 
	Zp field elements and gives a secret result shared over Zp.
	`greater_than_equal` method which can compare Zp field
	"""

	pp_elements = PreProcessedElements()
	modulus = Subgroup.BLS12_381
	Field = GF.get(modulus)
	l = num_digits(modulus, 2)
	k = security_parameter = 32

	async def get_random_bit():
		r = pp_elements.get_rand(context)
		r_square = await (r*r)
		r_sq = await r_square.open()

		if pow(r_sq, (modulus-1)//2) != Field(1) or r_sq ==0:
			return await get_random_bit()

		root = r_sq.sqrt()
		return (~Field(2)) * ((~root)*r + Field(1))

	# assert 2 * a_share + 1 < modulus, "[a] < (p-1)/2 must hold"
	# assert 2 * b_share + 1 < modulus, "[b] < (p-1)/2 must hold"

	# ############# PART 1 ###############
	# First Transformation
	r_bits = [pp_elements.get_bit(context) for _ in range(l)]
	r_B = Field(0)
	for i, b in enumerate(r_bits):
		r_B = r_B + (2**i) * b

	z = a_share - b_share
	c = await (2 * z + r_B).open()
	c_bits = [Field(int(x)) for x in list('{0:0b}'.format(c.value))]
	c_bits.reverse()

	r_0 = r_bits[0]		# [r0]
	c0 = c_bits[0]

	# ############# PART 2 ###############
	# Compute X
	X = Field(0)
	for i in range(l-1):
		cr = Field(0)
		for j in range(i+1, l):
			print(i, j)
			# print(i, j, "r_bits[j] ", await r_bits[j].open(), "c_bits[j] ", c_bits[j])
			c_xor_r = r_bits[j] + c_bits[j] - Field(2)*c_bits[j]*r_bits[j]
			# print("c_xor_r: ", await c_xor_r.open())
			cr = cr + c_xor_r
		cr_open = await cr.open()
		# print("cr: ", cr_open)
		pp = pow(2, int(cr_open))
		# print("pp: ", pp)
		X = X + (Field(1) - c_bits[i]) * pp * r_bits[i]

	# ############# PART 3 ###############
	# Extracting LSB
	# TODO
	# assert X.v.value < sqrt(4 * modulus)

	s_bits = [pp_elements.get_bit(context) for _ in range(l)]
	
	s_0 = s_bits[0]
	s1 = s_bits[-1]		# [s_{l-1}]	
	s2 = s_bits[-2]		# [s_{l-2}]
	s1s2 = await (s1*s2)

	s_B = Field(0)
	for i, b in enumerate(s_bits):
		s_B = s_B + (2**i) * b

	D = s_B + X
	d = await D.open()
	d0 = int(d) & 1

	# TODO
	# assert d > sqrt(4 * modulus)
	
	dxor1 = d0 ^ (d.value < 2**(l-1)) 	# d0 ^ (d < 2**{l-1})
	dxor2 = d0 ^ (d.value < 2**(l-2))	 # d0 ^ (d < 2**{l-1})
	dxor12 = d0 ^ (d.value < (2**(l-1) + 2**(l-2))) 		# d0 ^ (d < (2**{l-2} + 2**{l-1}))

	#[d_0]
	d_0 = d0 * (Field(1) + s1s2 - s1 - s2) \
		+ dxor2 * (s2 - s1s2) \
		+ dxor1 * (s1 - s1s2) \
		+ dxor12 * s1s2

	x_0 = s_0 + d_0 - 2 * (await (s_0 * d_0))	# [x0] = [s0] ^ [d0], equal to [r]B > c
	c0_xor_r0 = c0 + r_0 - 2*c0*r_0	#c0 ^ r_0
	return	c0_xor_r0 + x_0- 2*(await (c0_xor_r0*x_0)) #c0 ^ r_0 ^ x_0


async def test_comp(context):
	pp_elements = PreProcessedElements()
	a = pp_elements.get_zero(context) + context.Share(233)
	b = pp_elements.get_zero(context) + context.Share(23)

	r = pp_elements.get_rand(context)
	result = await comparison(context, a, b)

	if result:
		print("Comparison result: a > b")
	else:
		print("Comparison result: a <= b")

if __name__ == '__main__':
	n, t = 3, 1
	pp_elements = PreProcessedElements()
	logging.info('Generating random shares of zero in sharedata/')
	pp_elements.generate_zeros(1000, n, t)
	logging.info('Generating random shares in sharedata/')
	pp_elements.generate_rands(1000, n, t)
	# logging.info('Generating random shares of triples in sharedata/')
	# pp_elements.generate_triples(1000, n, t)
	logging.info('Generating random shares of bits in sharedata/')
	pp_elements.generate_bits(1000, n, t)

	asyncio.set_event_loop(asyncio.new_event_loop())
	loop = asyncio.get_event_loop()
	try:
		programRunner = TaskProgramRunner(n, t, {MixinOpName.MultiplyShare: BeaverTriple.multiply_shares})
		programRunner.add(test_comp)
		loop.run_until_complete(programRunner.join())
	finally:
		loop.close()