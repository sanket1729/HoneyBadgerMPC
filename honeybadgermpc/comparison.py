from honeybadgermpc.mpc import *
import logging
import asyncio
from honeybadgermpc.field import GF
from gmpy2 import num_digits
from honeybadgermpc.mixins import BeaverTriple, MixinOpName

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
		print("Value of r:", context.myid, await r.open())
		R = await r.open()
		r_square = await (r*r)
		r_sq = await r_square.open()

		print("R: ", R)
		print("R^2: ", r_sq)

		# if pow(r_sq, (modulus-1)//2) != Field(1):
		# 	return await get_random_bit()

		if r_sq ==0:
			return await get_random_bit()
		else:
			root = r_sq.sqrt()
			rrrr = (~root)*r
			print("root: ", root)
			print("~root: ", (~root))
			print("[r]: ", r)
			print("[r]/|r| = ", rrrr)
			aaaa = (~2) * ((~root)*r + Field(1))
			return aaaa

	cccc = await get_random_bit()
	print("cccc: ", cccc.v)

	return

	# assert 2 * a_share + 1 < modulus, "[a] < (p-1)/2 must hold"
	# assert 2 * b_share + 1 < modulus, "[b] < (p-1)/2 must hold"

	# ############# PART 1 ###############
	# First Transformation
	r_bits = [pp_elements.get_bit(context) for _ in range(l)]

	r_B = Field(0)
	for i, b in enumerate(r_bits):
		# print(i, b, (2**i) * b)
		r_B = r_B + (2**i) * b
		# print("======= r_B now === ", r_B)

	z = a_share - b_share
	c = await (2 * z + r_B).open()
	c_bits = [Field(int(x)) for x in list('{0:0b}'.format(c.value))]
	print(c_bits)
	c_bits.reverse()

	r_0 = r_bits[0]		# [r]0
	c0 = c_bits[0]

	# ############# PART 2 ###############
	# Compute X
	print("l: ", l)
	print("len(r_bits): ", len(r_bits))
	print("len(c_bits): ", len(c_bits))
	X = 0
	for i in range(l-1):
		cr = Field(0)
		for j in range(i+1, l):
			print(i, j, "r_bits[j] ", r_bits[j].v, "c_bits[j] ", c_bits[j])
			cr = cr + r_bits[j] + c_bits[j] - 2*c_bits[j]*r_bits[j]
		print("type(cr.v): ", type(cr.v.value), cr.v.value)
		pp = pow(2, cr.v.value)
		X = X + (Field(1) - c_bits[i]) * pp * r_bits[i]

	# ############# PART 3 ###############
	# Extracting LSB
	assert X < (4 * modulus).sqrt()

	s_bits = [pp_elements.get_bit(context) for _ in range(l)]
	
	s_0 = s_bits[0]
	s1 = s_bits[-1]		# [s_{l-1}]	
	s2 = s_bits[-2]		# [s_{l-2}]
	s1s2 = await (s1*s2)

	for i, b in enumerate(s_bits):
		s_B = s_B + b * 2**i

	D = s_B + X
	d = await D.open()
	d0 = d & 1

	# ???
	assert d > (4 * modulus).sqrt()
	
	dxor1 = d0 ^ (d < 2**(l-1)) 	# d0 ^ (d < 2**{l-1})
	dxor2 = d0 ^ (d < 2**(l-2))	 # d0 ^ (d < 2**{l-1})
	dxor12 = d0 ^ (d < (2**(l-1) + 2**(l-2))) 		# d0 ^ (d < (2**{l-2} + 2**{l-1}))

	#[d_0]
	d_0 = (1 - s1 - s2 + s1s2) * d0 \
		+ (s2 - s1s2) * dxor2 \
		+ (s1 - s1s2) * dxor1 \
		+ s1s2 * dxor12

	x_0 = s_0 ^ d_0 	# [x0], equal to [r]B > c
	return c0 ^ r_0 ^ x_0


async def test_comp(context):
	pp_elements = PreProcessedElements()
	a = pp_elements.get_zero(context) + context.Share(233)
	b = pp_elements.get_zero(context) + context.Share(23333)

	result = await comparison(context, a, b)

	if result:
		print("Comparison result: a > b")
	else:
		print("Comparison result: a <= b")

if __name__ == '__main__':
	pp_elements = PreProcessedElements()
	logging.info('Generating random shares of zero in sharedata/')
	pp_elements.generate_zeros(1000, 4, 1)
	logging.info('Generating random shares in sharedata/')
	pp_elements.generate_rands(1000, 4, 1)
	logging.info('Generating random shares of triples in sharedata/')
	pp_elements.generate_triples(1000, 4, 1)
	logging.info('Generating random shares of bits in sharedata/')
	pp_elements.generate_bits(1000, 4, 1)

	asyncio.set_event_loop(asyncio.new_event_loop())
	loop = asyncio.get_event_loop()
	try:
		logging.info("Start")
		programRunner = TaskProgramRunner(4, 1, {MixinOpName.MultiplyShare: BeaverTriple.multiply_shares})
		programRunner.add(test_comp)
		loop.run_until_complete(programRunner.join())
	finally:
		loop.close()