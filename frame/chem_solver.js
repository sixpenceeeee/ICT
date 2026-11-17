/* chem_solver.js — deterministic chemistry equation tools for offline pages.
 * Scope: balance user-supplied reactants/products; it does not predict products.
 * Formula parsing and nullspace elimination use exact integer/rational arithmetic.
 */
(function (root) {
  'use strict';

  var ELEMENTS = new Set(('H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr ' +
    'Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu ' +
    'Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg ' +
    'Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og').split(/\s+/));
  var SUBS = {'₀':'0','₁':'1','₂':'2','₃':'3','₄':'4','₅':'5','₆':'6','₇':'7','₈':'8','₉':'9'};
  var MAX_COEFFICIENT = 1000000, MAX_FORMULA_LENGTH = 160, MAX_SPECIES = 16;

  function fail(message) { throw new Error('化学方程式求解失败：' + message); }
  function gcd(a, b) { a = a < 0n ? -a : a; b = b < 0n ? -b : b; while (b) { var t = a % b; a = b; b = t; } return a; }
  function lcm(a, b) { return a === 0n || b === 0n ? 0n : (a / gcd(a, b)) * b; }
  function frac(n, d) {
    if (d === 0n) fail('矩阵消元遇到零分母');
    if (d < 0n) { n = -n; d = -d; }
    var g = gcd(n, d) || 1n;
    return {n:n/g, d:d/g};
  }
  function add(a, b) { return frac(a.n*b.d + b.n*a.d, a.d*b.d); }
  function sub(a, b) { return frac(a.n*b.d - b.n*a.d, a.d*b.d); }
  function mul(a, b) { return frac(a.n*b.n, a.d*b.d); }
  function div(a, b) { if (!b.n) fail('矩阵消元遇到零主元'); return frac(a.n*b.d, a.d*b.n); }
  function neg(a) { return {n:-a.n, d:a.d}; }

  function parseSegment(source, allowMultiplier) {
    var factor = 1;
    if (/^\d/.test(source)) {
      if (!allowMultiplier) fail('化学式开头不能带配平系数；水合物分段系数除外');
      var m = source.match(/^\d+/); factor = Number(m[0]); source = source.slice(m[0].length);
      if (!Number.isSafeInteger(factor) || factor <= 0) fail('水合物分段系数必须是正整数');
    }
    if (!source) fail('化学式中存在空分段');
    var closing = {'(':')','[':']'};
    function seq(index, expected) {
      var counts = Object.create(null);
      while (index < source.length) {
        var ch = source[index];
        if (ch === ')' || ch === ']') {
          if (expected !== ch) fail('化学式括号不匹配');
          return {counts:counts, index:index+1};
        }
        if (closing[ch]) {
          var inner = seq(index+1, closing[ch]); index = inner.index;
          if (!Object.keys(inner.counts).length) fail('化学式不能包含空括号');
          var start = index;
          while (index < source.length && /\d/.test(source[index])) index++;
          var mult = start < index ? Number(source.slice(start,index)) : 1;
          if (!Number.isSafeInteger(mult) || mult <= 0) fail('括号后的原子个数必须是正整数');
          Object.keys(inner.counts).forEach(function (el) { counts[el] = (counts[el] || 0) + inner.counts[el]*mult; });
          continue;
        }
        if (/[A-Z]/.test(ch)) {
          var begin = index++;
          while (index < source.length && /[a-z]/.test(source[index])) index++;
          var element = source.slice(begin,index);
          if (!ELEMENTS.has(element)) fail('未知元素符号：' + element);
          var n0 = index;
          while (index < source.length && /\d/.test(source[index])) index++;
          var amount = n0 < index ? Number(source.slice(n0,index)) : 1;
          if (!Number.isSafeInteger(amount) || amount <= 0) fail('原子个数必须是正整数');
          counts[element] = (counts[element] || 0) + amount;
          continue;
        }
        if (ch === ')' || ch === ']') fail('化学式括号不匹配');
        fail('化学式包含无法识别的字符：' + ch);
      }
      if (expected) fail('化学式括号未闭合');
      return {counts:counts,index:index};
    }
    var parsed = seq(0, null);
    if (parsed.index !== source.length || !Object.keys(parsed.counts).length) fail('无法解析化学式');
    var result = Object.create(null);
    Object.keys(parsed.counts).forEach(function (el) {
      var n = parsed.counts[el] * factor;
      if (!Number.isSafeInteger(n) || n > 1000000) fail('单种元素的原子数过大');
      result[el] = n;
    });
    return result;
  }

  function parseFormula(formula) {
    if (typeof formula !== 'string') fail('化学式必须是字符串');
    var text = formula.replace(/[₀₁₂₃₄₅₆₇₈₉]/g, function (ch) { return SUBS[ch]; }).replace(/\s/g, '');
    if (!text || text.length > MAX_FORMULA_LENGTH) fail('化学式不能为空且长度不能超过 ' + MAX_FORMULA_LENGTH + ' 个字符');
    var parts = text.split(/[·.]/), total = Object.create(null);
    if (parts.some(function (p) { return !p; })) fail('化学式中存在空水合物分段');
    parts.forEach(function (part, i) {
      var parsed = parseSegment(part, i > 0);
      Object.keys(parsed).forEach(function (el) { total[el] = (total[el] || 0) + parsed[el]; });
    });
    if (Object.keys(total).some(function (el) { return total[el] > 1000000; })) fail('单种元素的原子数过大');
    return total;
  }

  function species(raw, side, index) {
    var formula, charge = 0, phase = '';
    if (typeof raw === 'string') formula = raw;
    else if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
      formula = raw.formula || raw['化学式']; charge = raw.charge == null ? (raw['电荷'] == null ? 0 : raw['电荷']) : raw.charge;
      phase = String(raw.phase || raw['状态'] || '');
    } else fail(side + '第 ' + (index+1) + ' 个物质必须是化学式字符串或对象');
    if (typeof formula !== 'string' || !formula.trim()) fail(side + '第 ' + (index+1) + ' 个物质缺少 formula 化学式');
    if (!Number.isSafeInteger(charge) || Math.abs(charge) > 100) fail(side + '第 ' + (index+1) + ' 个物质的 charge 必须是 -100 到 100 的整数');
    formula = formula.trim();
    return {formula:formula, phase:phase, charge:charge, atoms:parseFormula(formula)};
  }

  function nullspace(matrix, columns) {
    var rows = matrix.map(function (row) { return row.map(function (v) { return frac(BigInt(v),1n); }); });
    var pivots = [], pivotRow = 0;
    for (var col = 0; col < columns; col++) {
      var candidate = -1;
      for (var r = pivotRow; r < rows.length; r++) if (rows[r][col].n !== 0n) { candidate = r; break; }
      if (candidate < 0) continue;
      var swap = rows[pivotRow]; rows[pivotRow] = rows[candidate]; rows[candidate] = swap;
      var pivot = rows[pivotRow][col];
      rows[pivotRow] = rows[pivotRow].map(function (v) { return div(v,pivot); });
      for (var rr = 0; rr < rows.length; rr++) {
        if (rr === pivotRow || rows[rr][col].n === 0n) continue;
        var scale = rows[rr][col];
        rows[rr] = rows[rr].map(function (v,j) { return sub(v,mul(scale,rows[pivotRow][j])); });
      }
      pivots.push(col); pivotRow++;
      if (pivotRow === rows.length) break;
    }
    var free = [];
    for (var c = 0; c < columns; c++) if (pivots.indexOf(c) < 0) free.push(c);
    if (free.length !== 1) fail('当前物质组合' + (free.length === 0 ? '没有非零配平解' : '存在多组配平解') + '，自由度为 ' + free.length);
    var vec = Array.from({length:columns}, function () { return frac(0n,1n); });
    vec[free[0]] = frac(1n,1n);
    pivots.forEach(function (col, row) { vec[col] = neg(rows[row][free[0]]); });
    return {rank:pivots.length, vector:vec};
  }

  function integerCoefficients(vector) {
    var denominator = vector.reduce(function (v,x) { return lcm(v,x.d); },1n);
    var values = vector.map(function (x) { return x.n*(denominator/x.d); });
    if (values.every(function (x) { return x < 0n; })) values = values.map(function (x) { return -x; });
    if (values.some(function (x) { return x <= 0n; })) fail('给定反应物和生成物无法形成所有系数均为正数的方程式');
    var common = values.reduce(gcd);
    values = values.map(function (x) { return x/common; });
    if (values.some(function (x) { return x > BigInt(MAX_COEFFICIENT); })) fail('最简系数超过安全上限 ' + MAX_COEFFICIENT);
    return values.map(Number);
  }

  function totals(items, coefficients) {
    var atoms = Object.create(null), charge = 0;
    items.forEach(function (item,i) {
      Object.keys(item.atoms).forEach(function (el) { atoms[el] = (atoms[el] || 0) + item.atoms[el]*coefficients[i]; });
      charge += item.charge*coefficients[i];
    });
    return {atoms:Object.keys(atoms).sort().reduce(function (out,el) { out[el] = atoms[el]; return out; },{}), charge:charge};
  }
  function show(items, coefficients) {
    return items.map(function (item,i) { return (coefficients[i] === 1 ? '' : coefficients[i]) + item.formula + (item.phase ? '(' + item.phase + ')' : ''); }).join(' + ');
  }
  function requestSides(request) {
    if (!request || typeof request !== 'object' || Array.isArray(request)) fail('配平方程式请求必须是对象');
    var l = request.reactants || request['反应物'], r = request.products || request['生成物'];
    if (!Array.isArray(l) || !Array.isArray(r) || !l.length || !r.length) fail('反应物和生成物两侧都必须至少包含一个物质');
    if (l.length+r.length > MAX_SPECIES) fail('物质种类总数不能超过 ' + MAX_SPECIES);
    return {left:l.map(function (x,i) { return species(x,'反应物',i); }), right:r.map(function (x,i) { return species(x,'生成物',i); })};
  }

  function balanceEquation(request) {
    var sides = requestSides(request), items = sides.left.concat(sides.right);
    var elements = Array.from(new Set(items.reduce(function (all,x) { return all.concat(Object.keys(x.atoms)); },[]))).sort();
    var hasCharge = items.some(function (item) { return item.charge !== 0; });
    var matrix = elements.map(function (el) { return items.map(function (item,i) { return (item.atoms[el] || 0)*(i < sides.left.length ? 1 : -1); }); });
    if (hasCharge) matrix.push(items.map(function (item,i) { return item.charge*(i < sides.left.length ? 1 : -1); }));
    var solved = nullspace(matrix,items.length), coeffs = integerCoefficients(solved.vector);
    var lc = coeffs.slice(0,sides.left.length), rc = coeffs.slice(sides.left.length);
    var left = totals(sides.left,lc), right = totals(sides.right,rc);
    var atomOk = JSON.stringify(left.atoms) === JSON.stringify(right.atoms), chargeOk = left.charge === right.charge;
    return {
      schema:'chem-equation-balance.v1', reactants:sides.left, products:sides.right,
      coefficients:{reactants:lc,products:rc},
      equation:show(sides.left,lc)+' → '+show(sides.right,rc),
      atom_counts:{left:left.atoms,right:right.atoms}, charge_counts:{left:left.charge,right:right.charge},
      elements:elements, rank:solved.rank, nullity:items.length-solved.rank,
      checks:{positive_integer_coefficients:coeffs.every(function(x){return Number.isInteger(x)&&x>0;}),
        primitive_coefficients:coeffs.reduce(function(a,b){return Number(gcd(BigInt(a),BigInt(b)));})===1,
        atoms_balanced:atomOk,charge_balanced:chargeOk,ok:atomOk&&chargeOk}
    };
  }

  function finiteRange(raw, label, minimum, maximum) {
    if (typeof raw === 'boolean' || raw == null || typeof raw === 'object' ||
        (typeof raw === 'string' && !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(raw.trim()))) {
      fail(label + '必须是有限数值');
    }
    var value = Number(raw);
    if (!Number.isFinite(value)) fail(label + '必须是有限数值');
    if (minimum != null && value < minimum) fail(label + '不能小于 ' + minimum);
    if (maximum != null && value > maximum) fail(label + '不能大于 ' + maximum);
    return value;
  }

  function amountTotals(items, amounts, elements) {
    var atoms = Object.create(null), charge = 0;
    elements.forEach(function (element) { atoms[element] = 0; });
    items.forEach(function (item,i) {
      elements.forEach(function (element) { atoms[element] += (item.atoms[element] || 0) * amounts[i]; });
      charge += item.charge * amounts[i];
    });
    return {atoms:atoms,charge:charge};
  }

  function conservation(initial, final) {
    var keys = Array.from(new Set(Object.keys(initial).concat(Object.keys(final)))).sort();
    var errors = Object.create(null), ok = true;
    keys.forEach(function (key) {
      var a = initial[key] || 0, b = final[key] || 0, error = Math.abs(a-b);
      errors[key] = error;
      if (error > Math.max(1e-12,Math.abs(a)*1e-10)) ok = false;
    });
    var initialOut = {}, finalOut = {}, errorsOut = {};
    keys.forEach(function (key) { initialOut[key] = initial[key] || 0; finalOut[key] = final[key] || 0; errorsOut[key] = errors[key]; });
    return {initial_mol:initialOut,final_mol:finalOut,absolute_error_mol:errorsOut,ok:ok};
  }

  function solveStoichiometry(request) {
    if (!request || typeof request !== 'object' || Array.isArray(request)) fail('反应计量请求必须是对象');
    var balanced = balanceEquation({reactants:request.reactants,products:request.products});
    var amountsRaw = request.initial_amounts_mol;
    if (!Array.isArray(amountsRaw) || amountsRaw.length !== balanced.reactants.length) fail('initial_amounts_mol 必须与反应物数量一致');
    var initial = amountsRaw.map(function (value,i) {
      return finiteRange(value,'反应物 '+balanced.reactants[i].formula+' 初始物质的量',0,1000000);
    });
    if (!initial.some(function (value) { return value > 0; })) fail('至少一种反应物的初始物质的量必须大于 0');
    var progress = finiteRange(typeof request.progress === 'undefined' ? 1 : request.progress,'反应进度',0,1);
    var coeffR = balanced.coefficients.reactants, coeffP = balanced.coefficients.products;
    var extents = initial.map(function (amount,i) { return amount / coeffR[i]; });
    var maxExtent = Math.min.apply(Math,extents);
    var extentTolerance = Math.max(1e-30,Math.abs(maxExtent)*1e-10);
    var limitingIndices = [];
    extents.forEach(function (value,i) { if (Math.abs(value-maxExtent) <= extentTolerance) limitingIndices.push(i); });
    var extent = maxExtent*progress;
    var consumed = coeffR.map(function (coefficient) { return coefficient*extent; });
    var remaining = [], noNegative = true;
    initial.forEach(function (amount,i) {
      var value = amount-consumed[i], tolerance = Math.max(1e-12,Math.abs(amount)*1e-10);
      if (value < 0 && Math.abs(value) <= tolerance) value = 0;
      else if (value < 0) noNegative = false;
      remaining.push(value);
    });
    var produced = coeffP.map(function (coefficient) { return coefficient*extent; });
    var elements = balanced.elements;
    var initialTotals = amountTotals(balanced.reactants,initial,elements);
    var remainingTotals = amountTotals(balanced.reactants,remaining,elements);
    var productTotals = amountTotals(balanced.products,produced,elements);
    var finalAtoms = Object.create(null);
    elements.forEach(function (element) { finalAtoms[element] = remainingTotals.atoms[element]+productTotals.atoms[element]; });
    var elementBalance = conservation(initialTotals.atoms,finalAtoms);
    var chargeBalance = conservation({charge:initialTotals.charge},{charge:remainingTotals.charge+productTotals.charge});
    var reactants = balanced.reactants.map(function (item,i) { return {
      index:i,formula:item.formula,phase:item.phase,coefficient:coeffR[i],
      initial_mol:initial[i],consumed_mol:consumed[i],remaining_mol:remaining[i]
    }; });
    var products = balanced.products.map(function (item,i) { return {
      index:i,formula:item.formula,phase:item.phase,coefficient:coeffP[i],produced_mol:produced[i]
    }; });
    var limiting = limitingIndices.map(function (i) { return {index:i,formula:balanced.reactants[i].formula}; });
    var checks = {
      equation_balanced:balanced.checks.ok,
      no_negative_remaining:noNegative,
      element_conservation:elementBalance.ok,
      charge_conservation:chargeBalance.ok,
      limiting_reagents_defined:limiting.length>0,
      ok:balanced.checks.ok&&noNegative&&elementBalance.ok&&chargeBalance.ok&&limiting.length>0
    };
    return {
      schema:'chem-stoichiometry.v1',equation:balanced.equation,coefficients:balanced.coefficients,
      initial_amounts_mol:initial,progress:progress,max_extent_mol:maxExtent,extent_mol:extent,
      limiting_reactants:limiting,stoichiometric_mix:limitingIndices.length===balanced.reactants.length,
      reactants:reactants,products:products,element_balance:elementBalance,
      charge_balance:chargeBalance,checks:checks
    };
  }

  function solutionVolumeUnit(raw) {
    if (typeof raw !== 'string') fail('体积单位必须是 mL 或 L');
    var key = raw.trim().toLowerCase();
    if (key === 'ml' || key === '毫升') return {unit:'mL',toLitre:0.001};
    if (key === 'l' || key === '升') return {unit:'L',toLitre:1};
    fail('不支持体积单位 ' + raw + '；只支持 mL 或 L');
  }

  function solveSolutionMixing(request) {
    if (!request || typeof request !== 'object' || Array.isArray(request)) fail('溶液混合请求必须是对象');
    var balanced = balanceEquation({reactants:request.reactants,products:request.products});
    var solutions = request.solutions;
    if (!Array.isArray(solutions) || solutions.length !== balanced.reactants.length) fail('solutions 数量必须与反应物数量一致');
    var rows = [], amounts = [];
    solutions.forEach(function (solution,i) {
      if (!solution || typeof solution !== 'object' || Array.isArray(solution)) fail('第 ' + (i+1) + ' 个溶液输入必须是对象');
      var formula = balanced.reactants[i].formula;
      var concentration = finiteRange(solution.concentration_mol_L,'反应物 '+formula+' 浓度',0,1000000);
      var volumeInput = finiteRange(solution.volume,'反应物 '+formula+' 体积',0,1000000);
      if (volumeInput === 0) fail('反应物 '+formula+' 的溶液体积必须大于 0');
      var volumeUnit = solutionVolumeUnit(solution.volume_unit);
      var volumeL = volumeInput * volumeUnit.toLitre;
      var amount = concentration * volumeL;
      if (!Number.isFinite(amount) || amount > 1000000) fail('反应物 '+formula+' 换算后的物质的量超过安全上限');
      amounts.push(amount);
      rows.push({index:i,formula:formula,concentration_mol_L:concentration,
        volume_input:volumeInput,volume_unit:volumeUnit.unit,volume_L:volumeL,amount_mol:amount});
    });
    var stoich = solveStoichiometry({reactants:request.reactants,products:request.products,
      initial_amounts_mol:amounts,progress:typeof request.progress === 'undefined' ? 1 : request.progress});
    var checks = Object.assign({},stoich.checks,{
      solution_inputs_valid:true,
      concentration_volume_conversion:rows.every(function (row) {
        return Math.abs(row.amount_mol-row.concentration_mol_L*row.volume_L) <=
          Math.max(1e-15,Math.abs(row.amount_mol)*1e-12);
      })
    });
    checks.ok = checks.ok && checks.solution_inputs_valid && checks.concentration_volume_conversion;
    return Object.assign({},stoich,{schema:'chem-solution-mixing.v1',solution_inputs:rows,checks:checks});
  }

  var PRECIPITATION_ATOMIC_MASSES = {
    H:1.008,C:12.011,N:14.007,O:15.999,Na:22.989769,Mg:24.305,
    S:32.06,Cl:35.45,Ca:40.078,Fe:55.845,Cu:63.546,Ag:107.8682,Ba:137.327
  };
  var PRECIPITATION_REACTIONS = [
    {id:'silver-chloride',reactants:['AgNO3','NaCl'],products:[['AgCl','s'],['NaNO3','aq']],
      precipitate:'AgCl',net:'Ag⁺(aq) + Cl⁻(aq) → AgCl(s)',ions:[['Ag',1],['Cl',-1]]},
    {id:'barium-sulfate',reactants:['BaCl2','Na2SO4'],products:[['BaSO4','s'],['NaCl','aq']],
      precipitate:'BaSO4',net:'Ba²⁺(aq) + SO₄²⁻(aq) → BaSO₄(s)',ions:[['Ba',2],['SO4',-2]]},
    {id:'calcium-carbonate',reactants:['CaCl2','Na2CO3'],products:[['CaCO3','s'],['NaCl','aq']],
      precipitate:'CaCO3',net:'Ca²⁺(aq) + CO₃²⁻(aq) → CaCO₃(s)',ions:[['Ca',2],['CO3',-2]]},
    {id:'copper-hydroxide',reactants:['CuSO4','NaOH'],products:[['Cu(OH)2','s'],['Na2SO4','aq']],
      precipitate:'Cu(OH)2',net:'Cu²⁺(aq) + 2OH⁻(aq) → Cu(OH)₂(s)',ions:[['Cu',2],['OH',-1]]},
    {id:'iron-iii-hydroxide',reactants:['FeCl3','NaOH'],products:[['Fe(OH)3','s'],['NaCl','aq']],
      precipitate:'Fe(OH)3',net:'Fe³⁺(aq) + 3OH⁻(aq) → Fe(OH)₃(s)',ions:[['Fe',3],['OH',-1]]},
    {id:'magnesium-hydroxide',reactants:['MgSO4','NaOH'],products:[['Mg(OH)2','s'],['Na2SO4','aq']],
      precipitate:'Mg(OH)2',net:'Mg²⁺(aq) + 2OH⁻(aq) → Mg(OH)₂(s)',ions:[['Mg',2],['OH',-1]]}
  ];
  function solvePrecipitation(request) {
    if (!request||typeof request!=='object'||Array.isArray(request)) fail('沉淀反应请求必须是对象');
    if (!Array.isArray(request.solutions)||request.solutions.length!==2) fail('首版必须提供两份溶液 solutions');
    var formulas=request.solutions.map(function(solution){
      if (!solution||typeof solution!=='object'||Array.isArray(solution)||typeof solution.formula!=='string'||!solution.formula.trim())
        fail('每份溶液都必须提供溶质化学式 formula');
      var formula=solution.formula.trim().replace(/[₀₁₂₃₄₅₆₇₈₉]/g,function(ch){return SUBS[ch];});
      parseFormula(formula); return formula;
    });
    if (formulas[0]===formulas[1]) fail('首版只支持两种不同溶质的混合');
    var reaction=PRECIPITATION_REACTIONS.find(function(row){
      return row.reactants.length===formulas.length&&row.reactants.every(function(formula){return formulas.indexOf(formula)>=0;});
    });
    if (!reaction) fail('该溶液组合不在首版沉淀反应目录中；请勿把未识别组合判为无沉淀');
    var solutionsByFormula=Object.create(null);
    formulas.forEach(function(formula,index){solutionsByFormula[formula]=request.solutions[index];});
    var reactants=reaction.reactants.map(function(formula){return {formula:formula,phase:'aq'};});
    var products=reaction.products.map(function(pair){return {formula:pair[0],phase:pair[1]};});
    var mixing=solveSolutionMixing({reactants:reactants,products:products,
      solutions:reaction.reactants.map(function(formula){return solutionsByFormula[formula];}),
      progress:typeof request.progress==='undefined'?1:request.progress});
    var precipitate=mixing.products.find(function(item){return item.formula===reaction.precipitate&&item.phase==='s';});
    if (!precipitate) fail('目录反应的沉淀必须是方程式中的固态生成物');
    var atoms=parseFormula(reaction.precipitate), molarMass=0;
    Object.keys(atoms).forEach(function(element){
      if (typeof PRECIPITATION_ATOMIC_MASSES[element]!=='number') fail('沉淀摩尔质量缺少元素原子量：'+element);
      molarMass+=PRECIPITATION_ATOMIC_MASSES[element]*atoms[element];
    });
    molarMass=Math.round(molarMass*1e9)/1e9;
    var netIonicBalance=balanceEquation({
      reactants:reaction.ions.map(function(ion){return {formula:ion[0],charge:ion[1],phase:'aq'};}),
      products:[{formula:reaction.precipitate,charge:0,phase:'s'}]
    });
    var moles=precipitate.produced_mol, mass=moles*molarMass;
    var checks=Object.assign({},mixing.checks,{
      catalog_reaction_recognized:true,precipitate_is_solid_product:true,
      net_ionic_equation_balanced:!!netIonicBalance.checks.ok,
      molar_mass_from_formula:Number.isFinite(molarMass)&&molarMass>0,
      precipitate_mass_calculation:Math.abs(mass-moles*molarMass)<=Math.max(1e-15,Math.abs(mass)*1e-12),
      nonnegative_precipitate:moles>=0&&mass>=0
    });
    checks.ok=Object.keys(checks).every(function(key){return checks[key]===true;});
    return Object.assign({},mixing,{schema:'chem-precipitation.v1',reaction_id:reaction.id,
      precipitate_formula:reaction.precipitate,precipitate_moles:moles,
      precipitate_molar_mass_g_mol:molarMass,precipitate_mass_g:mass,
      precipitation_occurs:moles>1e-15,net_ionic_equation:reaction.net,
      net_ionic_balance:netIonicBalance,checks:checks});
  }

  var KSP_MIN = 1e-80, KSP_MAX = 1e6, KSP_MAX_CONCENTRATION = 1e3, KSP_MAX_EXPONENT = 12;
  var KSP_SUPERSCRIPT = {'0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹','-':'⁻','+':'⁺'};
  function kspLogProduct(ions, concentrations) {
    var total = 0;
    for (var i=0;i<ions.length;i++) {
      if (concentrations[i] <= 0) return -Infinity;
      total += ions[i].coefficient * Math.log(concentrations[i]);
    }
    return total;
  }
  function kspExpClamped(logValue) {
    if (logValue === -Infinity || logValue < -745) return 0;
    if (logValue > Math.log(1e300)) return 1e300;
    return Math.exp(logValue);
  }
  function kspSolvePositiveSolubility(ions, background, logKsp) {
    function residual(logS) {
      var solubility = Math.exp(logS);
      return kspLogProduct(ions, background.map(function (initial,i) {
        return initial + ions[i].coefficient * solubility;
      })) - logKsp;
    }
    var low=-700, high=0;
    if (residual(low)>=0) fail('Ksp 太小，超出首版溶解度数值范围');
    while (residual(high)<0 && high<Math.log(1e6)) high=Math.min(high+Math.log(2),Math.log(1e6));
    if (residual(high)<0) fail('给定 Ksp 对应的溶解度超出首版数值范围');
    for (var step=0;step<180;step++) {
      var middle=(low+high)/2;
      if (residual(middle)<0) low=middle; else high=middle;
    }
    return Math.exp((low+high)/2);
  }
  function solveSolubilityEquilibrium(request) {
    if (!request||typeof request!=='object'||Array.isArray(request)) fail('溶解平衡请求必须是对象');
    var solidRaw=request.solid_formula||request.solid;
    if (typeof solidRaw!=='string'||!solidRaw.trim()) fail('必须提供难溶固体化学式 solid_formula');
    var solid=solidRaw.trim().replace(/[₀₁₂₃₄₅₆₇₈₉]/g,function(ch){return SUBS[ch];});
    var solidAtoms=parseFormula(solid), ksp=finiteRange(request.Ksp==null?request.ksp:request.Ksp,'Ksp',KSP_MIN,KSP_MAX);
    if (!Array.isArray(request.ions)||request.ions.length<2||request.ions.length>4)
      fail('ions 必须提供 2 到 4 种明确的溶解离子');
    var seen=new Set(), ions=[], atomTotal=Object.create(null), chargeTotal=0, exponentTotal=0;
    request.ions.forEach(function(raw,index){
      var label='第 '+(index+1)+' 种离子';
      if (!raw||typeof raw!=='object'||Array.isArray(raw)) fail(label+'必须是对象');
      if (typeof raw.formula!=='string'||!raw.formula.trim()) fail(label+'缺少 formula');
      var formula=raw.formula.trim().replace(/[₀₁₂₃₄₅₆₇₈₉]/g,function(ch){return SUBS[ch];});
      var atoms=parseFormula(formula), charge=raw.charge, coefficient=raw.coefficient;
      if (!Number.isSafeInteger(charge)||charge===0||Math.abs(charge)>12)
        fail(label+' charge 必须是 -12 到 12 之间的非零整数');
      if (!Number.isSafeInteger(coefficient)||coefficient<1||coefficient>6)
        fail(label+' coefficient 必须是 1 到 6 的整数');
      var key=formula+'|'+charge;
      if (seen.has(key)) fail('同种离子重复出现，请合并其系数'); seen.add(key);
      var concentration=finiteRange(typeof raw.initial_concentration_mol_L==='undefined'?0:raw.initial_concentration_mol_L,
        label+'初始浓度',0,KSP_MAX_CONCENTRATION);
      ions.push({formula:formula,charge:charge,coefficient:coefficient,
        initial_concentration_mol_L:concentration,atoms:atoms});
      exponentTotal+=coefficient; chargeTotal+=coefficient*charge;
      Object.keys(atoms).forEach(function(element){atomTotal[element]=(atomTotal[element]||0)+coefficient*atoms[element];});
    });
    if (exponentTotal>KSP_MAX_EXPONENT) fail('Ksp 总指数不能超过 '+KSP_MAX_EXPONENT);
    var atomKeys=Object.keys(atomTotal).sort(), solidKeys=Object.keys(solidAtoms).sort();
    if (JSON.stringify(atomKeys)!==JSON.stringify(solidKeys)||atomKeys.some(function(element){return atomTotal[element]!==solidAtoms[element];}))
      fail('离子及其系数合成的原子数与固体化学式不一致');
    if (chargeTotal!==0) fail('固体溶解离子的化学计量电荷和必须为 0');
    function displayIon(ion) {
      var formula=ion.formula.replace(/\d/g,function(d){return {'0':'₀','1':'₁','2':'₂','3':'₃','4':'₄','5':'₅','6':'₆','7':'₇','8':'₈','9':'₉'}[d];});
      var chargeText=(Math.abs(ion.charge)===1?'':String(Math.abs(ion.charge))).replace(/[0-9]/g,function(d){return KSP_SUPERSCRIPT[d];})+
        (ion.charge>0?'⁺':'⁻');
      return (ion.coefficient===1?'':ion.coefficient)+formula+chargeText+'(aq)';
    }
    var background=ions.map(function(ion){return ion.initial_concentration_mol_L;}), logQ=kspLogProduct(ions,background), logKsp=Math.log(ksp), difference=logQ-logKsp;
    var state,solubility,equilibriumConcentrations,logEqQ;
    if (difference>1e-10) {state='supersaturated';solubility=null;equilibriumConcentrations=null;logEqQ=null;}
    else if (difference>=-1e-10) {state='saturated';solubility=0;equilibriumConcentrations=background.slice();logEqQ=logQ;}
    else {
      state='unsaturated';solubility=kspSolvePositiveSolubility(ions,background,logKsp);
      equilibriumConcentrations=background.map(function(value,index){return value+ions[index].coefficient*solubility;});
      logEqQ=kspLogProduct(ions,equilibriumConcentrations);
    }
    var checks={solid_formula_matches_ions:true,dissolution_charge_balanced:chargeTotal===0,
      ion_product_classified:['unsaturated','saturated','supersaturated'].indexOf(state)>=0,
      mass_action_at_saturation:logEqQ==null?null:Math.abs(logEqQ-logKsp)<=1e-8,
      supersaturation_not_misrepresented_as_equilibrium:state!=='supersaturated'||logEqQ==null,
      no_negative_concentrations:background.every(function(value){return value>=0;})};
    checks.ok=Object.keys(checks).every(function(key){return checks[key]===true||checks[key]===null;});
    return {schema:'chem-solubility-ksp.v1',solid_formula:solid,Ksp:ksp,
      dissolution_equation:solid.replace(/\d/g,function(d){return {'0':'₀','1':'₁','2':'₂','3':'₃','4':'₄','5':'₅','6':'₆','7':'₇','8':'₈','9':'₉'}[d];})+'(s) ⇌ '+ions.map(displayIon).join(' + '),
      ions:ions.map(function(ion){return {formula:ion.formula,charge:ion.charge,coefficient:ion.coefficient,
        initial_concentration_mol_L:ion.initial_concentration_mol_L};}),
      initial_ion_product:kspExpClamped(logQ),initial_log_ion_product:Number.isFinite(logQ)?logQ:null,
      saturation_ratio:kspExpClamped(difference),saturation_state:state,molar_solubility_mol_L:solubility,
      equilibrium_ion_concentrations_mol_L:equilibriumConcentrations,
      equilibrium_ion_product:logEqQ==null?null:kspExpClamped(logEqQ),
      precipitation_expected:state==='supersaturated',assumes_excess_solid:true,checks:checks};
  }

  function titrationVolumeUnit(raw,label) {
    if (typeof raw !== 'string') fail(label+'单位必须是 mL 或 L');
    var key=raw.trim().toLowerCase();
    if (key==='ml'||key==='毫升') return {unit:'mL',toLitre:0.001};
    if (key==='l'||key==='升') return {unit:'L',toLitre:1};
    fail(label+'单位只支持 mL 或 L');
  }
  function titrationSolution(raw,label,allowZeroVolume) {
    if (!raw||typeof raw!=='object'||Array.isArray(raw)) fail(label+'输入必须是对象');
    var formula=raw.formula;
    var concentration=finiteRange(raw.concentration_mol_L,label+'浓度',0,1);
    if (concentration<=0) fail(label+'浓度必须大于 0');
    var volumeInput=finiteRange(raw.volume,label+'体积',0,1000000);
    if (volumeInput<=0&&!allowZeroVolume) fail(label+'体积必须大于 0');
    var unit=titrationVolumeUnit(raw.volume_unit,label), volumeL=volumeInput*unit.toLitre;
    var amount=concentration*volumeL;
    if (!Number.isFinite(amount)||amount>1000000) fail(label+'物质的量超过安全上限');
    return {formula:formula,concentration_mol_L:concentration,volume_input:volumeInput,
      volume_unit:unit.unit,volume_L:volumeL,amount_mol:amount};
  }
  function titrationClose(a,b,rel,abs) {
    return Math.abs(a-b)<=Math.max(abs,rel*Math.max(Math.abs(a),Math.abs(b)));
  }
  function solveAcidBaseTitration(request) {
    if (!request||typeof request!=='object'||Array.isArray(request)) fail('酸碱滴定请求必须是对象');
    var acid=titrationSolution(request.acid,'酸液',false);
    var base=titrationSolution(request.base,'碱液',true);
    var acidAnions={HCl:'Cl',HBr:'Br',HI:'I',HNO3:'NO3',HClO4:'ClO4'};
    var baseCations={LiOH:'Li',NaOH:'Na',KOH:'K'};
    if (typeof acid.formula!=='string'||!Object.prototype.hasOwnProperty.call(acidAnions,acid.formula))
      fail('当前只支持强一元酸 HCl、HBr、HI、HNO3、HClO4');
    if (typeof base.formula!=='string'||!Object.prototype.hasOwnProperty.call(baseCations,base.formula))
      fail('当前只支持强一元碱 LiOH、NaOH、KOH');
    var saltFormula=baseCations[base.formula]+acidAnions[acid.formula];
    var balanced=balanceEquation({reactants:[{formula:acid.formula,phase:'aq'},{formula:base.formula,phase:'aq'}],
      products:[{formula:saltFormula,phase:'aq'},{formula:'H2O',phase:'l'}]});
    if (JSON.stringify(balanced.coefficients)!==JSON.stringify({reactants:[1,1],products:[1,1]}))
      fail('该酸碱组合不符合当前 1:1 中和模型');
    var acidMol=acid.amount_mol, baseMol=base.amount_mol, reacted=Math.min(acidMol,baseMol);
    var acidRemaining=acidMol-reacted, baseRemaining=baseMol-reacted;
    var totalVolumeL=acid.volume_L+base.volume_L;
    if (!Number.isFinite(totalVolumeL)||totalVolumeL<=0) fail('混合后的总体积必须大于 0');
    var kw=1e-14, netAcid=(acidMol-baseMol)/totalVolumeL;
    var root=Math.sqrt(netAcid*netAcid+4*kw), hydrogen, hydroxide;
    if (netAcid>=0) { hydrogen=0.5*(netAcid+root); hydroxide=kw/hydrogen; }
    else { hydroxide=0.5*(-netAcid+root); hydrogen=kw/hydroxide; }
    var ph=-Math.log10(hydrogen), poh=-Math.log10(hydroxide);
    var balanceTolerance=Math.max(1e-15,Math.max(acidMol,baseMol)*1e-12);
    var state=acidMol-baseMol>balanceTolerance?'acidic':(baseMol-acidMol>balanceTolerance?'basic':'equivalence');
    var equivalenceVolumeL=acidMol/base.concentration_mol_L;
    var checks={
      equation_balanced:!!balanced.checks.ok,
      acid_mole_balance:titrationClose(acidMol,reacted+acidRemaining,1e-12,1e-15),
      base_mole_balance:titrationClose(baseMol,reacted+baseRemaining,1e-12,1e-15),
      nonnegative_excess:acidRemaining>=0&&baseRemaining>=0,
      water_ion_product:titrationClose(hydrogen*hydroxide,kw,1e-10,1e-24),
      ph_poh_sum:Math.abs(ph+poh-14)<=1e-10
    };
    checks.ok=Object.keys(checks).every(function(key){return checks[key]===true;})&&
      [ph,poh,hydrogen,hydroxide,equivalenceVolumeL,totalVolumeL].every(Number.isFinite);
    return {
      schema:'chem-acid-base-titration.v1',temperature_c:25,equation:balanced.equation,
      acid:acid,base:base,salt_formula:saltFormula,
      acid_moles_initial:acidMol,base_moles_added:baseMol,neutralized_moles:reacted,
      acid_moles_remaining:acidRemaining,base_moles_remaining:baseRemaining,
      equivalence_volume_l:equivalenceVolumeL,equivalence_volume_ml:equivalenceVolumeL*1000,
      total_volume_l:totalVolumeL,net_acid_concentration_mol_L:netAcid,
      excess_acid_concentration_mol_L:acidRemaining/totalVolumeL,
      excess_base_concentration_mol_L:baseRemaining/totalVolumeL,
      hydrogen_concentration_mol_L:hydrogen,hydroxide_concentration_mol_L:hydroxide,
      neutralization_fraction:reacted/acidMol,pH:ph,pOH:poh,state:state,checks:checks
    };
  }

  function checkCoefficients(request, coefficients) {
    var sides = requestSides(request);
    if (!coefficients || typeof coefficients !== 'object' || Array.isArray(coefficients)) fail('系数必须按 reactants/products 两侧提供');
    var left = coefficients.reactants, right = coefficients.products;
    if (!Array.isArray(left) || !Array.isArray(right) || left.length!==sides.left.length || right.length!==sides.right.length) fail('系数数量必须与方程式两侧物质数量一致');
    var values = left.concat(right);
    if (values.some(function (x) { return !Number.isSafeInteger(x) || x<=0 || x>MAX_COEFFICIENT; })) fail('系数必须是安全范围内的正整数');
    var lt = totals(sides.left,left), rt = totals(sides.right,right);
    var atomOk = JSON.stringify(lt.atoms)===JSON.stringify(rt.atoms), chargeOk = lt.charge===rt.charge;
    var common = values.reduce(function (a,b) { return Number(gcd(BigInt(a),BigInt(b))); });
    return {balanced:atomOk&&chargeOk,atoms_balanced:atomOk,charge_balanced:chargeOk,
      atom_counts:{left:lt.atoms,right:rt.atoms},charge_counts:{left:lt.charge,right:rt.charge},primitive:common===1};
  }

  var GAS_CONSTANT_L_KPA_PER_MOL_K = 8.31446261815324;
  function waterVaporPressureKpa(temperatureC) {
    temperatureC = finiteRange(temperatureC,'水上集气温度',0,100);
    var pressureMmhg = Math.pow(10,8.07131-1730.63/(233.426+temperatureC));
    return pressureMmhg*0.133322368;
  }
  function solveGasCollection(request) {
    if (!request||typeof request!=='object'||Array.isArray(request)) fail('气体收集请求必须是对象');
    if (typeof request.gas_formula!=='string'||!request.gas_formula.trim()) fail('必须指定目标气体 gas_formula');
    var gasFormula=request.gas_formula.trim();
    var temperatureC=finiteRange(request.temperature_c,'温度',-273.149,2000);
    var temperatureK=temperatureC+273.15;
    if (!(temperatureK>0)) fail('温度必须高于绝对零度');
    var totalPressure=finiteRange(request.total_pressure_kpa,'总压强',1e-9,100000);
    var method=typeof request.collection_method==='undefined'?'dry':request.collection_method;
    if (method!=='dry'&&method!=='over_water') fail('collection_method 只支持 dry 或 over_water');
    var reaction=solveStoichiometry({reactants:request.reactants,products:request.products,
      initial_amounts_mol:request.initial_amounts_mol,
      progress:typeof request.progress==='undefined'?1:request.progress});
    var matches=reaction.products.filter(function(item){return item.formula===gasFormula;});
    if (matches.length!==1) fail('目标气体必须且只能对应方程式中的一种生成物');
    var gas=matches[0], phase=String(gas.phase||'').trim().toLowerCase();
    if (['g','gas','气','气态'].indexOf(phase)<0) fail('目标气体生成物必须将 phase 标记为 g/gas/气态');
    var gasMoles=gas.produced_mol, vaporPressure=0, dryGasPressure=totalPressure;
    var vaporModel='none-dry-gas';
    if (method==='over_water') {
      vaporPressure=waterVaporPressureKpa(temperatureC);
      dryGasPressure=totalPressure-vaporPressure;
      if (!(dryGasPressure>0)) fail('总压强必须大于当前温度下水的饱和蒸气压');
      vaporModel='Antoine-0-to-100C';
    }
    var gasVolume=gasMoles*GAS_CONSTANT_L_KPA_PER_MOL_K*temperatureK/dryGasPressure;
    var idealPv=dryGasPressure*gasVolume;
    var idealNrt=gasMoles*GAS_CONSTANT_L_KPA_PER_MOL_K*temperatureK;
    var checks={
      reaction_balanced_and_conserved:!!reaction.checks.ok,
      target_is_single_gas_product:true,
      gas_amount_matches_product_yield:Math.abs(gasMoles-gas.produced_mol)<=Math.max(1e-15,Math.abs(gasMoles)*1e-12),
      partial_pressure_decomposition:Math.abs(totalPressure-dryGasPressure-vaporPressure)<=Math.max(1e-12,Math.abs(totalPressure)*1e-12),
      ideal_gas_relation:Math.abs(idealPv-idealNrt)<=Math.max(1e-15,Math.abs(idealNrt)*1e-12),
      nonnegative_volume:gasVolume>=0&&Number.isFinite(gasVolume)
    };
    checks.ok=Object.keys(checks).every(function(key){return checks[key]===true;});
    return Object.assign({},reaction,{
      schema:'chem-gas-collection.v1',gas_formula:gasFormula,gas_moles:gasMoles,
      temperature_c:temperatureC,temperature_k:temperatureK,total_pressure_kpa:totalPressure,
      collection_method:method,water_vapor_pressure_kpa:vaporPressure,
      dry_gas_partial_pressure_kpa:dryGasPressure,water_vapor_model:vaporModel,
      gas_constant_l_kpa_mol_k:GAS_CONSTANT_L_KPA_PER_MOL_K,gas_volume_l:gasVolume,checks:checks
    });
  }

  var REDOX_SUBSCRIPT = {'0':'₀','1':'₁','2':'₂','3':'₃','4':'₄','5':'₅','6':'₆','7':'₇','8':'₈','9':'₉'};
  var REDOX_SUPERSCRIPT = {'0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹'};
  var REDOX_FIXED = {Li:1,Na:1,K:1,Rb:1,Cs:1,Fr:1,Be:2,Mg:2,Ca:2,Sr:2,Ba:2,Ra:2,Al:3,Zn:2,Ag:1,F:-1};

  function redoxMedium(value) {
    if (typeof value !== 'string') fail('medium 必须明确指定 acidic/酸性 或 basic/碱性');
    var key = value.trim().toLowerCase();
    if (['acidic','acid','酸性'].indexOf(key) >= 0) return 'acidic';
    if (['basic','base','碱性','鹼性'].indexOf(key) >= 0) return 'basic';
    fail('medium 必须明确指定 acidic/酸性 或 basic/碱性');
  }

  function redoxNormalizeSpecies(raw,label) {
    if (typeof raw !== 'string' && (!raw || typeof raw !== 'object' || Array.isArray(raw))) fail(label+'必须是化学式或物质对象');
    if (typeof raw==='object'&&!Object.prototype.hasOwnProperty.call(raw,'charge')&&
        !Object.prototype.hasOwnProperty.call(raw,'电荷')) fail(label+'必须明确提供整数电荷 charge（中性物质也填 0）');
    var formula = typeof raw === 'string' ? raw : (raw.formula || raw['化学式']);
    var charge = typeof raw === 'string' ? 0 : (raw.charge == null ? (raw['电荷'] == null ? 0 : raw['电荷']) : raw.charge);
    if (typeof formula !== 'string' || !formula.trim()) fail(label+'缺少化学式');
    if (!Number.isSafeInteger(charge) || Math.abs(charge)>100) fail(label+'电荷必须是 -100 到 100 的整数');
    formula=formula.trim().replace(/[₀₁₂₃₄₅₆₇₈₉]/g,function(ch){return ({'₀':'0','₁':'1','₂':'2','₃':'3','₄':'4','₅':'5','₆':'6','₇':'7','₈':'8','₉':'9'})[ch];});
    var atoms=parseFormula(formula);
    if ((formula==='H'&&charge===1)||(formula==='OH'&&charge===-1)) fail('H+ 和 OH- 由溶液条件自动补入，请勿放入核心反应物');
    var phase=typeof raw==='string'?'':String(raw.phase||raw['状态']||'');
    return {formula:formula,charge:charge,phase:phase,atoms:atoms};
  }

  function redoxOxidationStates(item) {
    var atoms=item.atoms, elements=Object.keys(atoms), charge=item.charge, formula=item.formula;
    function requireIntegral(states) {
      elements.forEach(function(el){if(!Number.isInteger(states[el])) fail(formula+' 中存在平均氧化数，首版无法区分混合价态');});
      return states;
    }
    if (elements.length===1) { var only={}; only[elements[0]]=charge/atoms[elements[0]]; return requireIntegral(only); }
    var states=Object.create(null);
    elements.forEach(function(el){
      if (Object.prototype.hasOwnProperty.call(REDOX_FIXED,el)) states[el]=REDOX_FIXED[el];
      else if (el==='H') states[el]=1;
      else if (el==='O') states[el]=-2;
      else if (['Cl','Br','I'].indexOf(el)>=0&&!atoms.O&&!atoms.F) states[el]=-1;
    });
    if (atoms.O>=2 && elements.every(function(el){return el==='O'||Object.prototype.hasOwnProperty.call(states,el);})) {
      var nonO=elements.reduce(function(sum,el){return sum+(el==='O'?0:atoms[el]*states[el]);},0);
      var residue=charge-nonO;
      if (residue<0 && Math.abs(residue)<=atoms.O) states.O=residue/atoms.O;
    }
    var unknown=elements.filter(function(el){return !Object.prototype.hasOwnProperty.call(states,el);});
    if (!unknown.length) {
      var total=elements.reduce(function(sum,el){return sum+atoms[el]*states[el];},0);
      if (total!==charge) fail(formula+' 的常见氧化数规则与总电荷不符');
      return requireIntegral(states);
    }
    if (unknown.length!==1) fail('无法唯一判定 '+formula+' 中各元素氧化数；首版不支持该化学式');
    var el=unknown[0], knownTotal=elements.reduce(function(sum,key){return sum+(key===el?0:atoms[key]*states[key]);},0);
    states[el]=(charge-knownTotal)/atoms[el];
    return requireIntegral(states);
  }

  function redoxAnalysis(balanced) {
    var r=balanced.reactants,p=balanced.products,cr=balanced.coefficients.reactants,cp=balanced.coefficients.products;
    var elements=Array.from(new Set(r.concat(p).reduce(function(all,item){return all.concat(Object.keys(item.atoms));},[]))).sort();
    var sr=r.map(redoxOxidationStates),sp=p.map(redoxOxidationStates),changes=[],lost=0,gained=0;
    elements.forEach(function(element){
      var dr=[],dp=[];
      r.forEach(function(item,i){if(item.atoms[element])dr.push([sr[i][element],item.atoms[element]*cr[i]]);});
      p.forEach(function(item,i){if(item.atoms[element])dp.push([sp[i][element],item.atoms[element]*cp[i]]);});
      var nr=dr.reduce(function(a,x){return a+x[1];},0),np=dp.reduce(function(a,x){return a+x[1];},0);
      if(nr!==np) fail('元素 '+element+' 的反应物/生成物原子数不守恒');
      dr.sort(function(a,b){return a[0]-b[0];}); dp.sort(function(a,b){return a[0]-b[0];});
      var ri=0,pi=0,rl=dr.length?dr[0][1]:0,pl=dp.length?dp[0][1]:0;
      while(ri<dr.length&&pi<dp.length){
        var before=dr[ri][0],after=dp[pi][0],amount=Math.min(rl,pl),delta=after-before;
        if(Math.abs(delta)>1e-12){
          var lostHere=delta>0?amount*delta:0,gainedHere=delta<0?amount*-delta:0;
          lost+=lostHere; gained+=gainedHere;
          changes.push({element:element,atoms_per_reaction:amount,before:before,after:after,delta:delta,
            electrons_lost:lostHere,electrons_gained:gainedHere});
        }
        rl-=amount;pl-=amount;
        if(Math.abs(rl)<1e-12){ri++;if(ri<dr.length)rl=dr[ri][1];}
        if(Math.abs(pl)<1e-12){pi++;if(pi<dp.length)pl=dp[pi][1];}
      }
    });
    if(!changes.length||lost<=0||gained<=0) fail('输入物质中未识别到成对的氧化数升高与降低，不能判定为氧化还原反应');
    if(Math.abs(lost-gained)>Math.max(1e-12,Math.max(lost,gained)*1e-12)) fail('按氧化数独立计算的失电子与得电子不相等');
    return {changes:changes,lost:lost,gained:gained};
  }

  function redoxDisplay(items,coefficients) {
    return items.map(function(item,i){
      var formula=item.formula.replace(/\d/g,function(d){return REDOX_SUBSCRIPT[d];}),charge=item.charge;
      if(charge){var magnitude=Math.abs(charge)===1?'':String(Math.abs(charge)).replace(/\d/g,function(d){return REDOX_SUPERSCRIPT[d];});formula+=magnitude+(charge>0?'⁺':'⁻');}
      return (coefficients[i]===1?'':coefficients[i])+formula+(item.phase?'('+item.phase+')':'');
    }).join(' + ');
  }

  function solveRedox(request) {
    if(!request||typeof request!=='object'||Array.isArray(request)) fail('氧化还原请求必须是对象');
    var medium=redoxMedium(request.medium),rr=request.reactants,pp=request.products;
    if(!Array.isArray(rr)||!rr.length||!Array.isArray(pp)||!pp.length) fail('反应物和生成物两侧都必须提供核心物质数组');
    if(rr.length+pp.length>10) fail('核心物质种类总数不能超过 10');
    var nr=rr.map(function(x,i){return redoxNormalizeSpecies(x,'反应物第 '+(i+1)+' 项');});
    var np=pp.map(function(x,i){return redoxNormalizeSpecies(x,'生成物第 '+(i+1)+' 项');});
    nr.concat(np).forEach(redoxOxidationStates);
    [ ['反应物',nr], ['生成物',np] ].forEach(function(pair){
      var seen=new Set();pair[1].forEach(function(item){var k=item.formula+'|'+item.charge;if(seen.has(k))fail(pair[0]+'中有重复的同种物质，请合并后再输入');seen.add(k);});
    });
    var coreWater=nr.concat(np).some(function(item){return item.formula==='H2O'&&item.charge===0;});
    var waterChoices=coreWater?[0]:[0,1,-1],ionChoices=[0,1,-1],candidates=[],aux=medium==='acidic'?
      [['H2O',0,'l'],['H',1,'aq']]:[['H2O',0,'l'],['OH',-1,'aq']];
    waterChoices.forEach(function(ws){ionChoices.forEach(function(is){
      var left=[],right=[],count=0;
      [ws,is].forEach(function(side,index){if(!side)return;count++;
        var spec=aux[index],row={formula:spec[0],charge:spec[1],phase:spec[2]};(side===1?left:right).push(row);
      });
      try{
        var balanced=balanceEquation({reactants:rr.concat(left),products:pp.concat(right)});
        var analysis=redoxAnalysis(balanced),total=balanced.coefficients.reactants.concat(balanced.coefficients.products)
          .reduce(function(a,b){return a+b;},0);
        candidates.push({auxCount:count,total:total,balanced:balanced,analysis:analysis});
      }catch(e){}
    });});
    if(!candidates.length) fail('无法在指定酸碱条件下得到唯一且电子守恒的氧化还原方程式');
    candidates.sort(function(a,b){return a.auxCount-b.auxCount||a.total-b.total;});
    var chosen=candidates[0],balanced=chosen.balanced,analysis=chosen.analysis;
    var electronBalance={lost_electrons:analysis.lost,gained_electrons:analysis.gained,
      transferred_electrons:analysis.lost,ok:Math.abs(analysis.lost-analysis.gained)<=Math.max(1e-12,Math.max(analysis.lost,analysis.gained)*1e-12)};
    var checks={atoms_balanced:!!balanced.checks.atoms_balanced,charge_balanced:!!balanced.checks.charge_balanced,
      primitive_coefficients:!!balanced.checks.primitive_coefficients,oxidation_number_changes_detected:analysis.changes.length>0,
      electron_transfer_balanced:electronBalance.ok};
    checks.ok=Object.keys(checks).every(function(key){return checks[key]===true;});
    return {schema:'chem-redox.v1',medium:medium,
      equation:redoxDisplay(balanced.reactants,balanced.coefficients.reactants)+' → '+redoxDisplay(balanced.products,balanced.coefficients.products),
      coefficients:balanced.coefficients,reactants:balanced.reactants,products:balanced.products,
      oxidation_changes:analysis.changes,electron_balance:electronBalance,
      atom_counts:balanced.atom_counts,charge_counts:balanced.charge_counts,checks:checks};
  }

  root.CHEMSOLVER = {parseFormula:parseFormula,balanceEquation:balanceEquation,
    solveStoichiometry:solveStoichiometry,solveSolutionMixing:solveSolutionMixing,
    solveAcidBaseTitration:solveAcidBaseTitration,solveGasCollection:solveGasCollection,
    solvePrecipitation:solvePrecipitation,
    solveSolubilityEquilibrium:solveSolubilityEquilibrium,
    solveRedox:solveRedox,
    checkCoefficients:checkCoefficients};
})(typeof window !== 'undefined' ? window : globalThis);
