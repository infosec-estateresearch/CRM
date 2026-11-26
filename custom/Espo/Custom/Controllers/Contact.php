<?php

namespace Espo\Custom\Controllers;

use Espo\Core\Exceptions\Forbidden;

/**
 * CRM-IDINT-001 (3.4): contacts are never merged, because a merge ends by deleting
 * the source contacts. The merge action is refused before it starts, so it cannot
 * move any relationship first. The signature is deliberately wide so it fits the
 * parent's whatever its parameter list.
 */
class Contact extends \Espo\Modules\Crm\Controllers\Contact
{
    public function postActionMerge(mixed ...$arguments): never
    {
        throw new Forbidden('Contacts are never merged. Retire the duplicate or supersede it with the surviving contact.');
    }
}
