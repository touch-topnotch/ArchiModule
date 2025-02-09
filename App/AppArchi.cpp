//
// Created by Dmitry Tetkin on 04.02.2025.
//


#include "PreCompiled.h"
#include "Base/PyObjectBase.h"

#include <Base/Console.h>
#include <Base/Interpreter.h>


namespace Archi
{
class Module: public Py::ExtensionModule<Module>
{
public:
    Module()
        : Py::ExtensionModule<Module>("Archi")
    {
        initialize("This module is Archi module.");  // register with Python
    }

private:
    Py::Object simulateToFile(const Py::Tuple& args)
    {
       
        
        return Py::Float(0.0);
    }
};

PyObject* initModule()
{
    return Base::Interpreter().addModule(new Module);
}

}  // namespace Archi


/* Python entry */
PyMOD_INIT_FUNC(Archi)
{
    // clang-format off
    // load dependent module
    try {
        Base::Interpreter().runString("import Part");
    }
    catch(const Base::Exception& e) {
        PyErr_SetString(PyExc_ImportError, e.what());
        PyMOD_Return(nullptr);
    }

    PyObject* Archi = Archi::initModule();
    Base::Console().Log("Loading Archi module... done\n");

    // Add Types to module
   

    // NOTE: To finish the initialization of our own type objects we must
    // call PyType_Ready, otherwise we run into a segmentation fault, later on.
    // This function is responsible for adding inherited slots from a type's base class.

    
    PyMOD_Return(Archi);
    // clang-format on
}
