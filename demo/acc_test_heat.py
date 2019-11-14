import sys
sys.path.insert(0, "..")
import numpy as np
from reliability_analysis.akmcs import AKMCS,mcpopgen
from testcase.RA.testcase import evaluate
from surrogate_models.kriging_model import Kriging
from surrogate_models.kpls_model import KPLS
from surrogate_models.supports.initinfo import initkriginfo
from sensitivity_analysis.sobol_ind import SobolIndices as SobolI
import matplotlib.pyplot as plt
import time


def generate_krig(init_samp, n_krigsamp, nvar,problem):

    # Monte Carlo Sampling
    init_krigsamp = krigsamp()
    print("Evaluating Kriging Sample")
    ykrig = evaluate(init_krigsamp,problem)
    print(np.count_nonzero(ykrig <= 0))

    lb = (np.min(init_samp, axis=0))
    ub = (np.max(init_samp, axis=0))

    Pfreal = None

    # Set Kriging Info
    KrigInfo = initkriginfo("single")
    KrigInfo["X"] = init_krigsamp
    KrigInfo["y"] = ykrig
    KrigInfo["nvar"] = nvar
    KrigInfo["nsamp"] = n_krigsamp
    KrigInfo["nrestart"] = 5
    KrigInfo["ub"] = ub
    KrigInfo["lb"] = lb
    KrigInfo["nkernel"] = len(KrigInfo["kernel"])
    KrigInfo["n_princomp"] = 1
    KrigInfo["optimizer"] = "lbfgsb"

    #trainkrig
    drm = None
    t = time.time()
    krigobj = KPLS(KrigInfo, standardization=True, standtype='default', normy=False, trainvar=False)
    krigobj.train(parallel=False)
    loocverr, _ = krigobj.loocvcalc()
    elapsed = time.time() - t
    print("elapsed time for train Kriging model: ", elapsed, "s")
    print("LOOCV error of Kriging model: ", loocverr, "%")

    return krigobj,loocverr,drm

def krigsamp():
    all = mcpopgen(type="normal", ndim=53, n_order=2, n_coeff=1)
    return all

def pred(krigobj, init_samp, problem, drmmodel=None):

    nsamp = np.size(init_samp,axis=0)
    Gx = np.zeros(shape=[nsamp, 1])
    if nsamp < 10000:
        Gx = krigobj.predict(init_samp, ['pred'])
    else:
        run_times = int(np.ceil(nsamp / 10000))
        for i in range(run_times):
            start = i * 10000
            stop = (i + 1) * 10000
            if i != (run_times - 1):
                Gx[start:stop, :]=  krigobj.predict(init_samp[start:stop, :], ['pred'], drmmodel=drmmodel)
            else:
                Gx[start:, :] = krigobj.predict(init_samp[start:, :], ['pred'], drmmodel=drmmodel)

    init_samp_G = np.loadtxt('../innout/out/heatcond22.csv', delimiter=',').reshape(-1,1)

    subs = np.transpose((init_samp_G - Gx))
    subs1 = np.transpose((init_samp_G - Gx) / init_samp_G)
    RMSE = np.sqrt(np.sum(subs ** 2) / nsamp)
    RMSRE = np.sqrt(np.sum(subs1 ** 2) / nsamp)
    MAPE = 100 * np.sum(abs(subs1)) / nsamp
    print("RMSE = ", RMSE)
    print("MAPE = ", MAPE, "%")
    mean = np.mean(Gx)
    stdev = np.std(Gx)
    return MAPE, RMSE, mean, stdev

def sensitivity(krigobj,init_samp,nvar):
    lb = (np.min(init_samp, axis=0))
    ub = (np.max(init_samp, axis=0))
    lb = np.hstack((lb,lb))
    ub = np.hstack((ub,ub))
    testSA = SobolI(nvar, krigobj, None, ub, lb)
    result = testSA.analyze(True, True, False)
    for key in result.keys():
        print(key+':')
        if type(result[key]) is not dict:
            print(result[key])
        else:
            pass
            # for subkey in result[key].keys():
            #     print(subkey+':', result[key][subkey])

    return result


if __name__ == '__main__':
    init_samp = np.loadtxt('../innout/in/heat_samp2.csv', delimiter=',')
    dic = dict()

    for i in range(50):
        t1 = time.time()
        print("--"*25)
        print("loop no.",i+1)
        print("--" * 25)
        nvar = 53
        n_krigsamp = 50
        problem = 'heatcond'

        # Create Kriging model
        krigobj, loocverr, drm = generate_krig(init_samp, n_krigsamp, nvar, problem)
        # Predict and UQ
        MAPE, RMSE, mean, stdev = pred(krigobj, init_samp, problem, drmmodel=drm)
        # Sensitivity Analysis
        t = time.time()
        result = sensitivity(krigobj, init_samp, nvar)
        SAtime = time.time() - t

        # Create UQ and Acc test output file
        temparray = np.array([krigobj.KrigInfo['NegLnLike'], loocverr, RMSE, MAPE, mean, stdev, SAtime])
        if i == 0:
            totaldata = temparray[:]
        else:
            totaldata = np.vstack((totaldata, temparray))

        np.savetxt('../innout/out/acctest_heat_KPLS1.csv', totaldata, fmt='%10.5f', delimiter=',',
                   header='Neglnlike,LOOCV Error,RMSE,MAPE,Mean,Std Dev,SA time')

        # Create SA output file
        mylist = []
        for ii in range(53):
            mylist.append("S" + str(ii + 1) + ", ")
        for ii in range(52):
            mylist.append("St" + str(ii + 1) + ", ")
        mylist.append("St" + str(53))
        SAhead = ""
        for header in mylist:
            SAhead += header
        saresult = np.array([np.hstack((result['first'], result['total']))])
        if i == 0:
            sadata = saresult[:]
        else:
            sadata = np.vstack((sadata, saresult))
        np.savetxt('../innout/out/acctest_heat_KPLS1_SA.csv', sadata, fmt='%10.5f', delimiter=',',
                   header=SAhead)
        t2 = time.time() - t1
        print("Time for one loop: ",t2)
