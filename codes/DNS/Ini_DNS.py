import numpy as np
from scipy import io as sio
from math import pi
import sys
import os
from scipy.interpolate import interp1d as itp1d
from scipy.interpolate import interp2d as itp2d
from scipy.interpolate import griddata
from scipy.optimize import fsolve, brentq



def get_sl_interface(T2d, x, y, x_top, Tl):
    
    # T2d is 2d temperature
    # x : 1d array, e.g. x_dns
    # y : 1d array, e.g. y_dns
    # x_top: x-coordinate on the top boundary
    # Tl the temperature of your target interface
    # The solver loops over x_top, shoots a ray from x_top[j], and find the intersection with T=Tl
    # if no intersection is found, fill with nan.
    
    
    T_interp = itp2d(x, y, T2d.T)
    
    
    X = np.zeros(x_top.size)
    Y = np.zeros(x_top.size)
    
    for j in range(x_top.size):
        
        f = lambda s : T_interp(x_top[j], s) - Tl
        
        try:
        
            X[j] = x_top[j]
            Y[j] = brentq(f, y.min() ,0)
        except ValueError:
            
            X[j] = np.nan
            Y[j] = np.nan
        
    return X,Y


def psi_dns_initial( gradTx, gradTy, x,y, X,Y, max_len, Uitp ):
    
    # gradTx, gradTy : thermal gradient defined on the grid (x,y)
    # x: 1d array, eg. x_dns
    # y: 1d array, eg. y_dns
    # X,Y: initial s-l inteface obtained from get_sl_interface routine
    # max_len: maximum lenght of characteristics, use max( lx, ly )
    
    # eg. X_char, Y_char, psi_char = psi_dns_initial( gradTx_ini , gradTy_ini, x_dns, y_dns, X,Y , np.abs( x_dns[0] ) 
    
    yy, xx = np.meshgrid(y,x)
    
    # compute normal of s-l interface: X,Y
    nhat_x = np.zeros(X.size)
    nhat_y = np.zeros(Y.size)
    
    gx_interp = itp2d(x, y, gradTx.T, kind='linear')
    gy_interp = itp2d(x, y, gradTy.T, kind='linear')

    for j in range(X.size):

        vx = gx_interp(X[j],Y[j])
        vy = gy_interp(X[j],Y[j])
        vn = np.sqrt(vx**2+vy**2)
        
        nhat_x[j] = vx / vn
        nhat_y[j] = vy / vn
        
        
    # extend the interface beyond the left boundary
    hx = x[1] - x[0]
    npts_ext = int(  (X[0] - x[0])/ hx )
    x_ext = np.linspace( x[0] , X[0], npts_ext )
    
    
    f_sl = itp1d(X, Y, fill_value='extrapolate')
    y_ext = f_sl( x_ext )
    
    # compute normal of extended interface
    nhat_x_ext = -y_ext[1:] + y_ext[:-1]
    nhat_y_ext =  x_ext[1:] - x_ext[:-1]
    n2_ext = np.sqrt( nhat_x_ext**2 + nhat_y_ext**2 )
    nhat_x_ext = nhat_x_ext / n2_ext
    nhat_y_ext = nhat_y_ext / n2_ext

                
    # append extended interface with original 
    X = np.append(x_ext[:-1], X)
    Y = np.append(y_ext[:-1], Y)
    nhat_x = np.append(nhat_x_ext, nhat_x )
    nhat_y = np.append(nhat_y_ext, nhat_y)
    
    
    ds = x[1]-x[0]
    nstep = int(max_len / ds)
    
    
    X_char = np.zeros( (X.size, 2*nstep-1))
    Y_char = np.zeros( (X.size, 2*nstep-1))
    psi_char = np.zeros( (X.size, 2*nstep-1))
    U_char = np.zeros( (X.size, 2*nstep-1))
    
    for kk in range(nstep):
        
        
        if kk == 0:
            
            X_char[:,0] = X
            Y_char[:,0] = Y
            psi_char[:,0] = 0
            U_char[:,0] = Uitp(0)
        else:
        
            # follow characteristic in the dirction of the interior
            X_char[:,kk] = X_char[:,kk-1] + nhat_x * ds
            Y_char[:,kk] = Y_char[:,kk-1] + nhat_y * ds      
            psi_char[:,kk] = psi_char[:,kk-1] - ds
            U_char[:,kk] = Uitp(-ds*kk)
            
            # follow characteristic in the direction of the exterior
            X_char[:,-kk] = X_char[:,-kk+1] - nhat_x * ds
            Y_char[:,-kk] = Y_char[:,-kk+1] - nhat_y * ds      
            psi_char[:,-kk] = psi_char[:,-kk+1] + ds
            U_char[:,-kk] = Uitp(ds*kk)
    
    
    # # use the following for interpolation
    pts= np.array( ( X_char.flatten(), Y_char.flatten() ) ).T
        
    psi_val= psi_char.flatten()
    U_val = U_char.flatten()
    
    
    
    psi0 = griddata( pts, psi_val, ( xx, yy ), method = 'cubic')
    
    psi1 = griddata( pts, psi_val, ( xx, yy ), method = 'nearest')
    
    # # if there is nan, fill using nearest. 
    psi0[np.isnan(psi0)] = psi1[np.isnan(psi0)]
            
            
    # plt.scatter(X_char.flatten(), Y_char.flatten(), c = psi_char.flatten())
        
    # fig,ax=plt.subplots()
    # ax.pcolormesh( xx, yy , psi0)
    
    
    
    return pts, psi_val, U_val, psi_char, U_char



#macrodata = 'macrodata_Q200W_rb75.00um_ts0.50ms.mat'#
macrodata =  sys.argv[1]
dd = sio.loadmat(macrodata,squeeze_me=True)

# transient data
r1d = dd['z_1d'][:,-1]            # um
U1d = dd['Uc_1d'][:,-1]             # um
Ttip = dd['Ttip']
ztip = dd['ztip']





T_arr = dd['T_dns']
T_init = T_arr[:,:,0]
n_alpha0 = dd['alpha_dns']
xmac = dd['x_dns']
zmac = dd['y_dns']
gradTx = dd['gradTx_ini']
gradTy = dd['gradTy_ini']
X_arr = dd['X_arr']
Y_arr = dd['Y_arr']
thetas = dd['theta']

line_id = np.array([2,7,17])  # AM shallow
#line_id = np.array([4,13,29]) # Weld shallow

#line_id = np.array([4,15,28])
line_angle = thetas[line_id]; print(line_angle)
line_angle *= pi/180 
line_xst = X_arr[line_id,0]; line_yst = Y_arr[line_id,0]; 
T_interp = itp2d(xmac, zmac, T_init.T)

print('target tip temperature', Ttip)
for ii in range(len(line_id)):
  f = lambda s : T_interp(line_xst[ii]-s*np.cos(line_angle[ii]), line_yst[ii]-s*np.sin(line_angle[ii])) - Ttip
  dist_d = brentq(f, 0 , 100); print('dist to the tip curve',dist_d)
  line_xst[ii] = line_xst[ii]-dist_d*np.cos(line_angle[ii])
  line_yst[ii] = line_yst[ii]-dist_d*np.sin(line_angle[ii])
  print('the calibrated tip temp: ',  T_interp(line_xst[ii], line_yst[ii]))

xj_arr, yj_arr = get_sl_interface(T_init, xmac, zmac, xmac, Ttip)
xj_arr = xj_arr[~np.isnan(xj_arr)]; yj_arr = yj_arr[~np.isnan(yj_arr)]

print(xj_arr[0],yj_arr[0],xj_arr[-1],yj_arr[-1])

cent = (yj_arr[0]**2 + xj_arr[0]**2 - yj_arr[-1]**2)/(2*(-yj_arr[-1]+yj_arr[0]))
R0 = cent - yj_arr[-1]

print('approximated by a circle: center',cent, 'radius',R0)
print('how well the circle appoximation:')

err = 1- (xj_arr**2+ (cent - yj_arr)**2)/R0**2
print('the error', err)

max_len= xmac[-1]-xmac[0]
#extrapolate the U(r) profile to [-max_len, max_len] 
Umin = U1d[-1]; Umax = U1d[0]
r1d = -(r1d - ztip)    
r1d = np.hstack((max_len,r1d,-max_len))
U1d = np.hstack((Umax,U1d,Umin))

Uitp = itp1d(r1d, U1d)

#Txitp = itp2d(xmac,zmac,gradTx.T); gradTx = Txitp(xc,zc).T
#Tyitp = itp2d(xmac,zmac,gradTy.T); gradTy = Tyitp(xc,zc).T
points, psi_value, U_value, psi_char, U_char = psi_dns_initial( gradTx, gradTy, xmac,zmac, xj_arr,yj_arr, max_len, Uitp )


#plt.scatter(points[:,0],points[:,1])
# append data to macrodata
#del dd['X_char']; del dd['Y_char']; del dd['psi_char']
dd.update({'points':points,'psi_value':psi_value,'U_value':U_value,'line_angle':line_angle,'line_xst':line_xst,'line_yst':line_yst,'cent':cent,'R0':R0})
sio.savemat('AM_deep.mat',dd)





































