ruleFile = 'r2.tf.txt'
outFile = 'circ'
from os import listdir
from os.path import isfile, join
import math

TOTAL_NUM_HEADERS = 8 # number of headers in the header space

# builds a name of the .tf files in a directory
# returns a list of files 
def getTFNameList(dir_path):
	print("getting .tf file names from " + dir_path + " directory")
	files = [f for f in listdir(dir_path) if '.tf' in f]
	return files 

# takes in a list of .tf file names and a parent directory and extracts all the 
# rules of the files and a set of referenced port numbers in the files 
# returns a list of rulesDicts and a set of port nums 
def getSetOfPortNumsAndRules(dir_path, fileNameList):
	print("extracting port numbers from files in " + dir_path)
	ports = set()
	allRuleDicts = []
	for f in fileNameList:
		# one particular .tf file (router)
		fullPath = dir_path + '/' + f
		print(fullPath)
		tempFile = open(fullPath)
		Lines = tempFile.readlines()
		ruleDicts = []
		# extract rules in dictionary form 
		for line in Lines[2:]:
			rule = line.strip()
			rd = convert_rule_to_dict(rule)
			ruleDicts.append(rd)
		# extract input and output port numbers from rules string
		portsList = []
		for r in ruleDicts:
			listStrIn = r["inputPort"]
			# convert string rep of list to actual list
			portsList.append(listStrIn.strip('][').split(', '))
			# update rule dict entry
			r["inputPort"] =  listStrIn.strip('][').split(', ')
	
			# do the same for output port 
			listStrOut = r["outputPort"]
			portsList.append(listStrOut.strip('][').split(', '))
			r["outputPort"] = listStrOut.strip('][').split(', ')

		# finally, add port numbers to set
		for pList in portsList:
			for i in pList:
				ports.add(int(i))
		allRuleDicts.append(ruleDicts)
	return (ports, allRuleDicts)

# takes in a TF rule in dictionary form, and generates 
# code for the QC that checks the header bits
# outputs to a file 
def gen_header_bit_checker(ruleDict):

	idStr = ruleDict["id"]
	fString = outFile + idStr + ".txt"
	f = open(fString, 'w')

	header = ruleDict["headerMatch"]
	print("header:", header)
	# array specifying where the X gates on check bits should be 
	xGateArr = []
	# iterate through header to specify the X gates and length of bit checker
	for s in header:
		if s == "1":
			xGateArr.append('O')
		elif s == "0":
			xGateArr.append('X')
	bitCheckerSize = len(xGateArr)
	print("check gates:", xGateArr)
	
	# output code

	# defining the registers and circuits 
	f.write("inpt = QuantumRegister(%d, 'in')\n"%bitCheckerSize)
	f.write("check = QuantumRegister(%d, 'check')\n"%bitCheckerSize)
	f.write("e = QuantumRegister(%d, 'e')\n"%bitCheckerSize)
	f.write("res = QuantumRegister(1, 'res')\n")
	f.write("c = ClassicalRegister(1, 'c')\n")

	f.write("qc = QuantumCircuit(inpt, check, e, res, c)\n")


	# properly place the check bit X gates
	checkBitStartWire = bitCheckerSize
	wireInd = checkBitStartWire
	for i in range(len(xGateArr)):
		if xGateArr[i] == 'O':
			pass
		else:
			f.write("qc.x(%d)\n"%wireInd)
		wireInd += 1

	# input cnots 
	wireInd = 0
	for i in range(bitCheckerSize):
		f.write("qc.cx(%d,%d)\n"%(wireInd, wireInd + 2*bitCheckerSize))
		wireInd += 1
	# check cnots
	wireInd = bitCheckerSize
	for i in range(bitCheckerSize):
		f.write("qc.cx(%d,%d)\n"%(wireInd, wireInd + bitCheckerSize))
		wireInd += 1

	# AND gate 
	andStr = "["
	for i in range(bitCheckerSize):
		if i == bitCheckerSize - 1:
			andStr += "1]"
		else:
			andStr += "1,"
	f.write("A = AND(%d,%s)\n"%(bitCheckerSize,andStr))

	# append AND gate
	andWireInd = 2*bitCheckerSize
	andAppendStr = "[" + str(andWireInd) + ","
	andWireInd += 1
	for i in range(bitCheckerSize):
		if i == bitCheckerSize - 1:
			andAppendStr += str(andWireInd) + "]"
		else:
			andAppendStr += str(andWireInd) + ","
		andWireInd += 1
	f.write("qc.append(A,%s)\n"%andAppendStr)

	# measure, draw
	measWire = 3*bitCheckerSize
	f.write("qc.measure([%d],[0])\n"%measWire)
	f.write("qc.draw(output='mpl')\n")

	f.close()

# takes in a string defining a TF rule and outputs 
# rule in dictionary form 
# returns a rule dictionary with input/output port lists in string representation 
def convert_rule_to_dict(rule):
	s = rule.split('$')
	rDict = {}


	rDict["action"] = s[0]
	rDict["inputPort"] = s[1]
	rDict["headerMatch"] = s[2]
	rDict["outputPort"] = s[7]
	rDict["id"] = s[-2]

	return rDict

# converts an integer to its binary string of a certian length
def convertIntToBinaryStr(n, length):
	print("converting", n, "to length", length, "binary string")
	if n == 1 and length < 2:
		print("fatal error converting binary string-- length param too short!")
		exit()
	elif n > 1 and length < math.floor(math.log(n-1,2))+1:
		print("fatal error converting binary string-- length param too short!")
		exit()
	# first, build min length binary rep
	returnStr = ''
	while n > 0:
		rem = n % 2
		returnStr = str(rem) + returnStr
		n = n // 2
	l = len(returnStr)
	for i in range(length - l):
		returnStr = '0' + returnStr
	print(returnStr)
	return returnStr

# takes two equal-length binary strings, and returns a list
# of indices to swap 
def computeCXList(inputBinStr, outputBinStr):
	cxList = []
	for i in range(len(inputBinStr)):
		if inputBinStr[i] == outputBinStr[i]:
			cxList.append('O')
		else:
			cxList.append('X')
	return cxList


# code that takes in a single .tf file in the current directory and only looks at
# the forwarding match/action rules and generates 
# the qiskit code for the corresponding quantum circuit 
def genFowrardingCirc():
	# 
	path = "./"
	# get rules set of unique ports from .tf files in directory  
	tfFileNames = getTFNameList(path)
	print(tfFileNames)
	ports, rulesDicts = getSetOfPortNumsAndRules(path, tfFileNames)

	# total number of unique ports 
	numUniquePorts = len(ports)

	print("port numbers: ", ports)
	print("total unique port numbers:")
	print(numUniquePorts)

	#total number of unique headers
	print("total unique headers:", TOTAL_NUM_HEADERS)

	# create mapping of portNums to decimal number
	portNumMap = {}
	l = 0
	for p in ports:
		key = str(p)
		portNumMap[p] = l
		l += 1
	print("port num map: ", portNumMap)
	# only one rules dict for now (single .tf file) 
	print("rules dict: ", rulesDicts[0])

	# total number of rules in the .tf file 
	numRules = len(rulesDicts[0])

	# total number of qubits we'll need for forwarding circuit 
	numRouterBits = 2 if numUniquePorts == 1 else math.floor(math.log(numUniquePorts-1, 2)) + 1 # num bits to encode router port num 
	numRouterCheckBits = numUniquePorts * numRouterBits # num check bits for router ports
	
	numHeaderBits = 2 if TOTAL_NUM_HEADERS == 1 else math.floor(math.log(TOTAL_NUM_HEADERS-1, 2)) + 1
	numHeaderCheckBits = TOTAL_NUM_HEADERS * numHeaderBits

	# numHeaderBits = math.ceil(math.log(TOTAL_NUM_HEADERS, 2)) # num bits to encode header
	# numHeaderCheckBits = TOTAL_NUM_HEADERS * numHeaderBits # num check bits for header ports
	
	# ancilla bits
	numRouterCheckAncillas = numUniquePorts * (math.ceil(math.log(numUniquePorts, 2)) + 1)
	numHeaderCheckAncillas = TOTAL_NUM_HEADERS * (math.ceil(math.log(TOTAL_NUM_HEADERS, 2))+1)

	# forwarding rule ancilla bits
	numFwdAncillas = numRules

	print(numRules, numRouterBits, numRouterCheckBits, numHeaderBits, numHeaderCheckBits, numRouterCheckAncillas, numHeaderCheckAncillas)

	print("writing output to file")

	# start writing to output file
	outfileStr = "prog.txt"
	f = open(outfileStr, 'w')
	f.write("# ***Defining Quantum registers***\n\n")	
	f.write("router = QuantumRegister(%d, 'r')\n"%numRouterBits)
	f.write("router_check = QuantumRegister(%d, 'rc')\n"%numRouterCheckBits)
	f.write("header = QuantumRegister(%d, 'h')\n"%numHeaderBits)
	f.write("header_check = QuantumRegister(%d, 'hc')\n"%numHeaderCheckBits)
	f.write("rc_ancillas = QuantumRegister(%d, 'rca')\n"%numRouterCheckAncillas)
	f.write("hc_ancillas = QuantumRegister(%d, 'hca')\n"%numHeaderCheckAncillas)
	f.write("fwd_ancillas = QuantumRegister(%d, 'fwd')\n"%numFwdAncillas)
	f.write("qc = QuantumCircuit(router, router_check, header, header_check, rc_ancillas, hc_ancillas, fwd_ancillas)\n")

	# cnot gates from router bits and router check bits to the check ancillas
	f.write("# ***Router bit-checker circuit***\n\n")
	router_start_index = 0
	check_start_index = router_start_index + numRouterBits
	rca_start_index = numRouterBits + numRouterCheckBits + numHeaderBits + numHeaderCheckBits

	# same for header
	header_start_index = router_start_index + numRouterBits + numRouterCheckBits
	header_check_start_index = header_start_index + numHeaderBits
	hca_start_index = rca_start_index + numRouterCheckAncillas

	fwd_start_index = hca_start_index + numHeaderCheckAncillas

	shift = 0
	checkshift = 0

	# X gates for the router bit checkers
	for i in range(numUniquePorts):
		binStr = convertIntToBinaryStr(i, numRouterBits)
		print("router bin str:", binStr)
		for j in range(numRouterBits):
			if binStr[j] == "0":
				f.write("qc.x(%d)\n"%(check_start_index + checkshift))
			checkshift += 1

	checkshift = 0 
	# X gates for the header bit checkers
	for i in range(TOTAL_NUM_HEADERS):
		binStr = convertIntToBinaryStr(i, numHeaderBits)
		print("header bin str:", binStr)
		for j in range(numHeaderBits):
			if binStr[j] == "0":
				f.write("qc.x(%d)\n"%(header_check_start_index + checkshift))
			checkshift += 1

	# router and check CX gates
	checkshift = 0
	for i in range(numUniquePorts):
		for j in range(numRouterBits):
			f.write("qc.cx(%d,%d)\n"%(router_start_index+j,rca_start_index+j+shift))
			f.write("qc.cx(%d,%d)\n"%(check_start_index+checkshift+j,rca_start_index+j+shift))
		shift += numRouterBits + 1
		checkshift += numRouterBits


	# same for header 
	shift = 0 
	checkshift = 0
	for i in range(TOTAL_NUM_HEADERS):
		for j in range(numHeaderBits):
			f.write("qc.cx(%d,%d)\n"%(header_start_index+j,hca_start_index+j+shift))
			f.write("qc.cx(%d,%d)\n"%(header_check_start_index+checkshift+j,hca_start_index+j+shift))
		shift += numHeaderBits + 1
		checkshift += numHeaderBits
	
			

	# AND gates for the router bit checkers 
	router_and_start_index = rca_start_index
	shift = 0 
	for i in range(numUniquePorts):
		# initialize AND gate
		andStr = "["
		for j in range(numRouterBits):
			if j == numRouterBits - 1:
				andStr += "1]"
			else:
				andStr += "1,"
		f.write("A = AND(%d,%s)\n"%(numRouterBits,andStr))
		# place AND gate
		
		andAppendStr = "[" + str(router_and_start_index + shift) + ","
		for k in range(numRouterBits):
			if k == numRouterBits - 1:
				andAppendStr += str(router_and_start_index + shift + k + 1) + "]"
			else:
				andAppendStr += str(router_and_start_index + shift + k + 1) + ","
		f.write("qc.append(A,%s)\n"%andAppendStr)
		shift += numRouterBits + 1

	# AND gates for the header bit checkers 
	header_and_start_index = hca_start_index
	shift = 0 
	for i in range(TOTAL_NUM_HEADERS):
		# initialize AND gate
		andStr = "["
		for j in range(numHeaderBits):
			if j == numHeaderBits - 1:
				andStr += "1]"
			else:
				andStr += "1,"
		f.write("A = AND(%d,%s)\n"%(numHeaderBits,andStr))
		# place AND gate
		
		andAppendStr = "[" + str(header_and_start_index + shift) + ","
		for k in range(numHeaderBits):
			if k == numHeaderBits - 1:
				andAppendStr += str(header_and_start_index + shift + k + 1) + "]"
			else:
				andAppendStr += str(header_and_start_index + shift + k + 1) + ","
		f.write("qc.append(A,%s)\n"%andAppendStr)
		shift += numHeaderBits + 1

	# apply the logic of the forwarding rules!

	f.write("# ***Router forwarding logic***\n\n")
	# just one rules dict for now (one .tf file)
	rulesDict = rulesDicts[0]
	fwdShift = 0 
	shift = 0
	for i in range(len(rulesDict)):
		rule = rulesDict[i]
		print("scanning rule",rule['id'])
		inputPortStr = int(rule["inputPort"][0]) # get input port as string
		# convert input port through mapping
		inputPortInt = portNumMap[inputPortStr]

		outputPortStr = int(rule["outputPort"][0]) # get output port as string
		# convert input port through mapping
		outputPortInt = portNumMap[outputPortStr]
		print("in/out ports:", inputPortInt, outputPortInt)

		# get header as string and int 
		headerMatchStr = rule["headerMatch"][:numHeaderBits]
		headerInt = int(headerMatchStr, 2)

		# determine the router checker output index this corresponds to in circuit 
		rtrOutput = router_and_start_index + numRouterBits + (numRouterBits+1)*(inputPortInt)
		print("router checker output bit index:", rtrOutput)

		# determine header checker output index this corresponds to in circuit 
		hdrOutput = header_and_start_index + numHeaderBits + (numHeaderBits+1)*(headerInt)
		print(header_start_index, numHeaderBits, headerInt)
		print("header checker output bit index:", hdrOutput)

		# add fwd logic AND gates
		# initialize AND gate
		andStr = "["
		for j in range(2):
			if j == 1:
				andStr += "1]"
			else:
				andStr += "1,"
		f.write("A = AND(%d,%s)\n"%(2,andStr))
		# place AND gate
		
		andAppendStr = "[" + str(rtrOutput) + "," + str(hdrOutput) + "," + str(fwd_start_index + shift) + "]"
		# for k in range(numHeaderBits):
		# 	if k == numHeaderBits - 1:
		# 		andAppendStr += str(header_and_start_index + shift + k + 1) + "]"
		# 	else:
		# 		andAppendStr += str(header_and_start_index + shift + k + 1) + ","
		f.write("qc.append(A,%s)\n"%andAppendStr)
		shift += 1

		# must query a function to determine which router bits must be swapped
		# (a function of input port and output port)
		inputBinStr = convertIntToBinaryStr(inputPortInt, numRouterBits)
		outputBinStr = convertIntToBinaryStr(outputPortInt, numRouterBits)
		cxList = computeCXList(inputBinStr, outputBinStr)
		print("router cx gates list:", cxList)
		# apply the relevant ccx gates
		for i in range(len(cxList)):
			if cxList[i] == 'O':
				continue
			else:
				f.write("qc.cx(%d,%d)\n"%(fwd_start_index + fwdShift,router_start_index + i))

		fwdShift += 1
		
	f.write("\n")
	f.write("qc.draw(output='mpl')\n")
	f.close()

# ************ #
# main routine 
# ************ #

if __name__ == "__main__":


	# generate the code for a .tf file that just contains header match/forwarding ops 
	genFowrardingCirc()

